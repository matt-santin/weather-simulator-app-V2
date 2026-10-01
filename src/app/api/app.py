"""The HTTP layer: two endpoints and three pages, no state.

    uvicorn src.app.api.app:app --port 8000

``/api/config`` serves the constants the form shares with the API: served
periods, maximum range, temperature scale, geocoding address. ``/api/days``
reads one series from the store and returns the classified days.

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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from starlette.responses import Response

from src.app.api import errors, pipeline, validation
from src.app.api.contract import Series
from src.app.domain import thresholds
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
    yield


app = FastAPI(
    title="Weather Simulator V2",
    summary="Météo journalière : réanalyse ERA5 (1970-2005) et simulation CORDEX corrigée "
    "(2027-2100). Ce n'est pas une prévision.",
    lifespan=lifespan,
)


class Coverage(BaseModel):
    start: str
    end: str
    origin: str


class Config(BaseModel):
    geocoding_url: str
    coverage_start: str
    coverage_end: str
    periods: list[Coverage]
    max_days: int
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
