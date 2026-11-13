"""The HTTP layer: the endpoints of the API and four pages, no state.

    uvicorn src.app.api.app:app --port 8765

``/api/config`` serves the constants the form shares with the API: served
periods, maximum range, temperature scale, geocoding address. ``/api/days``
reads one series from the store and returns the classified days;
``/api/normals`` serves the seasonal normals of the same dates (1971-2000,
1981-2010 or 1991-2020). ``/api/climate`` serves the climate diagram
of the place around the year searched. ``/api/years`` serves the same dates in every
year from 1970 to 2100; ``/api/kinds`` sorts the seasons of each epoch of the
home form into cool, normal and warm. ``/api/map/cells`` and ``/api/map/{name}`` serve the
maps of the page /cartes (src.app.maps), when the map store is there;
``/api/place`` names the town nearest a point clicked on a map (places.py).

The store is opened at start-up, not on the first visit: a missing or
unfinished array stops the boot rather than failing on a visitor. Geocoding
stays in the browser (Open-Meteo, limited per visitor's address).
"""

from __future__ import annotations

import hashlib
import html
import re
from contextlib import asynccontextmanager
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from starlette.responses import Response

from src.app import maps
from src.app.api import climate, errors, kinds, normals, pipeline, places, summary, validation, years
from src.app.api.contract import Climate, Kinds, Normals, Place, Series, Summary, Years
from src.app.domain import thresholds
from src.app.maps import MapStore
from src.app.store import PERIODS, Simulation, Store

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEB = Path(__file__).resolve().parents[3] / "web"


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store()


# A test substitutes its own store through app.dependency_overrides[get_store].
StoreDep = Annotated[Store, Depends(get_store)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store()
    get_map_store()
    get_places()
    yield


app = FastAPI(
    title="Weather Simulator V2",
    summary="Météo journalière : réanalyse ERA5 et observations E-OBS (1970-2025), simulation CORDEX corrigée "
    "(2027-2100). Ce n'est pas une prévision.",
    lifespan=lifespan,
)

# The maps travel as megabytes of integers that compress threefold; the JSON
# answers gain too. Under a kilobyte, compressing costs more than it saves.
app.add_middleware(GZipMiddleware, minimum_size=1000)

# An answer of the API only changes when a store is rebuilt or the server's code
# is: it may be kept an hour without asking (a browser, a cache in front of the
# server), then asked again with its mark, and a mark that still holds is
# answered 304 before anything is read. The maps, the heaviest, keep their day.
API_CACHE = "public, max-age=3600"


@lru_cache(maxsize=1)
def _code_mark() -> str:
    """The server's own files, hashed: new code is a new answer, same store or not."""
    digest = hashlib.sha1()
    for path in sorted(Path(__file__).resolve().parents[1].rglob("*.py")):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _dependency(dependency):
    """What the endpoints are given for ``dependency``: a test's substitute, or it."""
    return app.dependency_overrides.get(dependency, dependency)()


def api_mark() -> str:
    """The ETag of every answer of the API: the stores as built, the list of
    places, the code. Weak: the same answer travels compressed or not."""
    store, map_store, found = (_dependency(d) for d in (get_store, get_map_store, get_places))
    parts = (store.built, map_store.built if map_store else "", found.stamp if found else "",
             _code_mark())
    return 'W/"' + hashlib.sha1("|".join(parts).encode()).hexdigest()[:20] + '"'


@app.middleware("http")
async def cache_api(request: Request, call_next):
    if request.method != "GET" or not request.url.path.startswith("/api/"):
        return await call_next(request)
    mark = api_mark()
    if mark in request.headers.get("if-none-match", ""):
        return Response(status_code=304, headers={"ETag": mark, "Cache-Control": API_CACHE})
    response = await call_next(request)
    if response.status_code == 200:
        response.headers["ETag"] = mark
        response.headers.setdefault("Cache-Control", API_CACHE)
    return response


class Coverage(BaseModel):
    start: str
    end: str
    origin: str


class Reference(BaseModel):
    first: int
    label: str


class EpochInfo(BaseModel):
    id: str
    first: int
    last: int


class SimulationInfo(BaseModel):
    """The CORDEX run served from 2027, as the store describes it."""

    model: str
    source: str
    driving: str
    regional: str
    institute: str
    domain: str
    scenario: str
    calibration_start: str
    calibration_end: str


class Config(BaseModel):
    geocoding_url: str
    coverage_start: str
    coverage_end: str
    periods: list[Coverage]
    max_days: int
    normals: list[Reference]
    normals_default: int
    temperature_band_edges: list[float]
    temperature_band_step: float
    epochs: list[EpochInfo]
    epochs_default: str
    simulation: SimulationInfo
    # The frame of the map page (maps.BOX), or None without a map store: the
    # results page links to the map only where it shows the place.
    map_box: dict[str, float] | None


@lru_cache(maxsize=1)
def get_map_store() -> MapStore | None:
    found = maps.open_store()
    if found is not None and found.simulation != get_store().simulation:
        raise RuntimeError(f"{maps.STORE}: simulation {found.simulation.model}, "
                           f"le site sert {get_store().simulation.model}")
    return found


MapStoreDep = Annotated[MapStore | None, Depends(get_map_store)]


@app.get("/api/config", response_model=Config)
def config(store: StoreDep, map_store: MapStoreDep) -> Config:
    sim = store.simulation
    return Config(
        geocoding_url=GEOCODING_URL,
        coverage_start=PERIODS[0].start.isoformat(),
        coverage_end=PERIODS[-1].end.isoformat(),
        periods=[
            Coverage(
                start=p.start.isoformat(),
                end=p.end.isoformat(),
                origin="simulated" if p.source == "cordex" else "observed",
            )
            for p in PERIODS
        ],
        max_days=validation.MAX_DAYS,
        normals=[Reference(first=f, label=normals.label(f)) for f in normals.REFERENCES],
        normals_default=normals.DEFAULT,
        temperature_band_edges=list(thresholds.TEMPERATURE_BAND_EDGES),
        temperature_band_step=thresholds.TEMPERATURE_BAND_STEP_C,
        epochs=[EpochInfo(id=e.id, first=e.first, last=e.last) for e in kinds.EPOCHS],
        epochs_default=kinds.DEFAULT,
        map_box=dict(maps.BOX) if map_store is not None else None,
        simulation=SimulationInfo(
            model=sim.model,
            source=sim.source,
            driving=sim.driving,
            regional=sim.regional,
            institute=sim.institute,
            domain=sim.domain,
            scenario=sim.scenario,
            calibration_start=sim.calibration_start.isoformat(),
            calibration_end=sim.calibration_end.isoformat(),
        ),
    )


@app.get("/api/days", response_model=Series)
def days(
    store: StoreDep,
    latitude: Annotated[float, Query()],
    longitude: Annotated[float, Query()],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
) -> Series:
    try:
        search = validation.Search(latitude=latitude, longitude=longitude, start=start, end=end)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
    cell = store.cell(search.latitude, search.longitude)
    if cell is None:
        raise errors.OutsideDomain(search.latitude, search.longitude)
    return pipeline.run(store, search.period, cell, search.start, search.end)


def located(store: Store, latitude: float, longitude: float, start: date, end: date,
            reference: int):
    """The checks the normals and the climate diagram share with a search, plus
    the reference period. Returns the search and the cell."""
    if reference not in normals.REFERENCES:
        labels = [normals.label(f) for f in normals.REFERENCES]
        raise errors.UnknownReference(reference, ", ".join(labels[:-1]) + " et " + labels[-1])
    try:
        search = validation.Search(latitude=latitude, longitude=longitude, start=start, end=end)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
    cell = store.cell(search.latitude, search.longitude)
    if cell is None:
        raise errors.OutsideDomain(search.latitude, search.longitude)
    return search, cell


@app.get("/api/normals", response_model=Normals)
def seasonal_normals(
    store: StoreDep,
    latitude: Annotated[float, Query()],
    longitude: Annotated[float, Query()],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    reference: Annotated[int, Query()] = normals.DEFAULT,
) -> Normals:
    """The normals of the dates of a search, under the same rules, over the
    30 years starting in ``reference`` (normals.REFERENCES)."""
    search, cell = located(store, latitude, longitude, start, end, reference)
    return normals.run(store, cell, search.start, search.end, reference)


@app.get("/api/climate", response_model=Climate)
def climate_diagram(
    store: StoreDep,
    latitude: Annotated[float, Query()],
    longitude: Annotated[float, Query()],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    reference: Annotated[int, Query()] = normals.DEFAULT,
) -> Climate:
    """The climate diagram of the place over the 15 years around the year of the
    search (climate.window), beside the reference period."""
    search, cell = located(store, latitude, longitude, start, end, reference)
    middle = search.start + (search.end - search.start) / 2
    return climate.run(store, cell, middle.year, reference)


@app.get("/api/years", response_model=Years)
def every_year(
    store: StoreDep,
    latitude: Annotated[float, Query()],
    longitude: Annotated[float, Query()],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    reference: Annotated[int, Query()] = normals.DEFAULT,
) -> Years:
    """The dates of the search in every year from 1970 to 2100, beside the
    reference period (years.run)."""
    search, cell = located(store, latitude, longitude, start, end, reference)
    return years.run(store, cell, search.start, search.end, reference)


@app.get("/api/summary", response_model=Summary)
def search_summary(
    store: StoreDep,
    latitude: Annotated[float, Query()],
    longitude: Annotated[float, Query()],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    reference: Annotated[int, Query()] = normals.DEFAULT,
) -> Summary:
    """A few figures of the dates of the search beside their normal (summary.run)."""
    search, cell = located(store, latitude, longitude, start, end, reference)
    return summary.run(store, cell, search.start, search.end, reference)


@app.get("/api/kinds", response_model=Kinds)
def season_kinds(
    store: StoreDep,
    latitude: Annotated[float, Query()],
    longitude: Annotated[float, Query()],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
) -> Kinds:
    """The years of each epoch of the home form, sorted into cool, normal and
    warm seasons over the dates of the search (kinds.run)."""
    search, cell = located(store, latitude, longitude, start, end, normals.DEFAULT)
    return kinds.run(store, cell, search.start, search.end)


# --- the maps ----------------------------------------------------------------



@lru_cache(maxsize=1)
def get_places() -> places.Places | None:
    return places.open_places()


PlacesDep = Annotated[places.Places | None, Depends(get_places)]


@app.get("/api/place", response_model=Place)
def nearest_place(
    found: PlacesDep,
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
) -> Place:
    """The town nearest a point, for the map page: a cell clicked is given its name."""
    if found is None:
        raise errors.PlacesUnavailable()
    near = found.nearest(latitude, longitude)
    if near is None:
        return Place(name=None, country=None, distance_km=None)
    return Place(name=near["name"], country=near["country"], distance_km=near["distance_km"])


@app.get("/api/map/cells")
def map_cells(store: MapStoreDep) -> dict:
    """The land cells every map is drawn on, sent once."""
    if store is None:
        raise errors.MapsUnavailable()
    return store.cells()


@app.get("/api/map/isobars")
def map_isobars(
    store: MapStoreDep,
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
) -> Response:
    """Sea-level pressure over the map's box at 0.5 deg, days x rows x columns,
    little-endian 16-bit integers in tenths of a hPa (-32768: no value), for the
    isobars the browser draws. The grid travels in headers."""
    if store is None:
        raise errors.MapsUnavailable()
    if not store.isobars:
        raise errors.UnknownMapVariable("isobars")
    try:
        dates = validation.Range(start=start, end=end)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
    source = dates.period.source
    values, grid = store.pressure(source, dates.start, dates.end)
    return Response(
        content=values.tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Days": str(values.shape[0]),
            "X-Rows": str(values.shape[1]),
            "X-Cols": str(values.shape[2]),
            "X-North": str(grid["north"]),
            "X-West": str(grid["west"]),
            "X-Step": str(grid["step"]),
            "X-Start": dates.start.isoformat(),
            "X-Origin": "simulated" if source == "cordex" else "observed",
            "Cache-Control": "public, max-age=86400",
        },
    )


@app.get("/api/map/{name}")
def map_days(
    store: MapStoreDep,
    name: str,
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
) -> Response:
    """Days x cells of one variable, as little-endian 16-bit integers in tenths of
    its unit (deg C, mm, %; -32768 where there is no value), the cells in the
    order of /api/map/cells. What the browser needs to read them travels in headers."""
    if store is None:
        raise errors.MapsUnavailable()
    if name not in store.variables:
        raise errors.UnknownMapVariable(name)
    try:
        dates = validation.Range(start=start, end=end)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
    source = dates.period.source
    values = store.read(source, name, dates.start, dates.end)
    return Response(
        content=values.tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Days": str(values.shape[0]),
            "X-Cells": str(values.shape[1]),
            "X-Start": dates.start.isoformat(),
            "X-Origin": "simulated" if source == "cordex" else "observed",
            "Cache-Control": "public, max-age=86400",
        },
    )


# --- the pages and their files -----------------------------------------------

# Ask before reusing: the copy is kept, and a file that has not moved comes back
# as a 304. Without it the browser may reuse an edited module without asking.
REVALIDATE = {"cache-control": "no-cache"}


class RevalidatedStatic(StaticFiles):
    def file_response(self, *args: object, **kwargs: object) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers.update(REVALIDATE)
        return response


# What the scenario means for emissions, in the GIEC's words: RCP4.5 one of
# the two intermediate scenarios of AR5 (SYR, SPM 2.1), SSP3-7.0 the high one of
# AR6 (WGI, SPM, B.1.2). A scenario missing here gets no qualifier.
SCENARIO_LEVELS = {
    "RCP 4.5": ", une trajectoire intermédiaire",
    "SSP3-7.0": ", une trajectoire d'émissions élevées",
}


def fill_simulation(page: str, sim: Simulation) -> str:
    """The page with {{driving}}, {{scenario}}... replaced by the simulation the
    store serves, escaped, spaces made non-breaking. An unknown name is an error."""
    values = {
        "driving": sim.driving,
        "driving_id": sim.driving_id,
        "member": sim.member,
        "regional": sim.regional,
        "regional_id": sim.regional_id,
        "institute": sim.institute,
        "domain": sim.domain,
        "scenario": sim.scenario,
        "provider": sim.provider,
        "calibration": f"{sim.calibration_start.year}-{sim.calibration_end.year}",
        "scenario_level": SCENARIO_LEVELS.get(sim.scenario, ""),
    }
    return re.sub(r"\{\{(\w+)\}\}",
                  lambda m: html.escape(values[m.group(1)]).replace(" ", "&nbsp;"), page)


def mount_web(target: FastAPI, directory: Path = WEB) -> bool:
    """Serve the pages, when web/ sits next to the package. Says whether it did."""
    if not directory.is_dir():
        return False

    target.mount("/static", RevalidatedStatic(directory=directory / "static"), name="static")

    @target.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(directory / "pages" / "home.html", headers=REVALIDATE)

    @target.get("/resultats", include_in_schema=False)
    def results() -> FileResponse:
        return FileResponse(directory / "pages" / "results.html", headers=REVALIDATE)

    @target.get("/cartes", include_in_schema=False)
    def maps_page() -> FileResponse:
        return FileResponse(directory / "pages" / "maps.html", headers=REVALIDATE)

    @target.get("/documentation", include_in_schema=False)
    def documentation(store: StoreDep) -> HTMLResponse:
        page = (directory / "pages" / "documentation.html").read_text()
        return HTMLResponse(fill_simulation(page, store.simulation), headers=REVALIDATE)

    return True


mount_web(app)


# --- how a refusal reaches the visitor ---------------------------------------


@app.exception_handler(errors.ApiError)
def _api_error(request: Request, error: errors.ApiError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"message": error.message})


@app.exception_handler(RequestValidationError)
def _malformed(request: Request, error: RequestValidationError) -> JSONResponse:
    """A search the form should never have sent: a bad latitude, a missing field."""
    return JSONResponse(
        status_code=422,
        content={
            "message": "Recherche invalide : la localisation ou les dates sont mal formées.",
            "detail": jsonable_encoder(error.errors()),
        },
    )
