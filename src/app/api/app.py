"""The HTTP layer: seven endpoints and four pages, no state.

    uvicorn src.app.api.app:app --port 8000

``/api/config`` serves the constants the form shares with the API: served
periods, maximum range, temperature scale, geocoding address. ``/api/days``
reads one series from the store and returns the classified days;
``/api/normals`` serves the seasonal normals of the same dates (1971-2000,
1981-2010 or 1991-2020). ``/api/climate`` serves the climate diagram
of the place around the year searched. ``/api/years`` serves the same dates in every
year from 1970 to 2100. ``/api/map/cells`` and ``/api/map/{name}`` serve the
maps of the page /cartes (src.app.maps), when the map store is there.

The store is opened at start-up, not on the first visit: a missing or
unfinished array stops the boot rather than failing on a visitor. Geocoding
stays in the browser (Open-Meteo, limited per visitor's address).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from starlette.responses import Response

from src.app import maps
from src.app.api import climate, errors, normals, pipeline, validation, years
from src.app.api.contract import Climate, Normals, Series, Years
from src.app.domain import thresholds
from src.app.maps import MapStore
from src.app.store import PERIODS, Store

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
    yield


app = FastAPI(
    title="Weather Simulator V2",
    summary="Météo journalière : réanalyse ERA5 (1970-2025) et simulation CORDEX corrigée "
    "(2027-2100). Ce n'est pas une prévision.",
    lifespan=lifespan,
)

# The maps travel as megabytes of integers that compress threefold; the JSON
# answers gain too. Under a kilobyte, compressing costs more than it saves.
app.add_middleware(GZipMiddleware, minimum_size=1000)


class Coverage(BaseModel):
    start: str
    end: str
    origin: str


class Reference(BaseModel):
    first: int
    label: str


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


@app.get("/api/config", response_model=Config)
def config() -> Config:
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


# --- the maps ----------------------------------------------------------------

@lru_cache(maxsize=1)
def get_map_store() -> MapStore | None:
    return maps.open_store()


MapStoreDep = Annotated[MapStore | None, Depends(get_map_store)]


@app.get("/api/map/cells")
def map_cells(store: MapStoreDep) -> dict:
    """The land cells every map is drawn on, sent once."""
    if store is None:
        raise errors.MapsUnavailable()
    return store.cells()


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
    def documentation() -> FileResponse:
        return FileResponse(directory / "pages" / "documentation.html", headers=REVALIDATE)

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
