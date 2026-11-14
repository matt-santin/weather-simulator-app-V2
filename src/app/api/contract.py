"""The JSON contract: one object per day, and what travels alongside them.

Kept from V1, so that the interface reads it unchanged, with three differences:
no ``wind_speed_max`` (CORDEX serves the daily mean wind only), no forecast
origin, and ``grid`` now describes the CORDEX correction rather than V1's
cloud-cover table.

It carries the sky class, never the pictogram; the temperature band, never the
colour; ``origin`` on every day and ``has_simulated`` on the response, which
the warning turns on. It omits ``temperature_mean``: an input of the snow
criterion, not displayed. The relative humidity, long omitted on the same
grounds, travels since 2026-10-17, when the enlarged card began to show it.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from src.app.domain import humidity, temperature
from src.app.domain.records import DailyRecord, Origin
from src.app.domain.sky import SkyClass


class Day(BaseModel):
    """One day, ready to display. Every measured field is nullable: a gap stays a gap."""

    date: date
    origin: Origin = Field(description="observed (ERA5) or simulated (corrected CORDEX)")
    source: str = Field(description="Which dataset served the day")

    temperature_min: float | None = Field(default=None, description="degrees Celsius")
    temperature_max: float | None = Field(default=None, description="degrees Celsius")
    precipitation: float | None = Field(default=None, description="millimetres, all phases")
    cloud_cover: float | None = Field(default=None, description="percent, daily mean")
    relative_humidity_mean: float | None = Field(
        default=None, description="percent, daily mean at 2 m"
    )
    wind_speed_mean: float | None = Field(default=None, description="km/h, daily mean at 10 m")
    wet_bulb_mean: float | None = Field(
        default=None, description="degrees Celsius, daily mean wet bulb (Stull)"
    )
    humid_heat: int | None = Field(
        default=None, description="0, 1 or 2, the humid-heat level; null without a reading"
    )
    sky: SkyClass | None = Field(
        default=None, description="clear, cloudy, overcast, rain or snow; null for a gap"
    )
    temperature_min_band: int | None = Field(
        default=None, description=f"0 to {temperature.BAND_COUNT - 1}, band of the minimum"
    )
    temperature_max_band: int | None = Field(default=None, description="band of the maximum")

    @classmethod
    def from_record(cls, record: DailyRecord, sky: SkyClass | None) -> Day:
        """Values are rounded on the way out, after every rule has read the full ones."""
        low_band, high_band = temperature.bands_of(record)
        wet_bulb = humidity.wet_bulb_of_record(record)
        return cls(
            date=record.date,
            origin=record.origin,
            source=record.source or "",
            temperature_min=rounded(record.temperature_min),
            temperature_max=rounded(record.temperature_max),
            precipitation=rounded(record.precipitation),
            cloud_cover=rounded(record.cloud_cover),
            relative_humidity_mean=rounded(record.relative_humidity_mean),
            wind_speed_mean=rounded(record.wind_speed_mean),
            wet_bulb_mean=rounded(wet_bulb),
            humid_heat=humidity.humid_heat(wet_bulb),
            sky=sky,
            temperature_min_band=low_band,
            temperature_max_band=high_band,
        )


def rounded(value: float | None) -> float | None:
    """One decimal, a gap left a gap: how every figure of the contract travels."""
    return None if value is None else round(value, 1)


class Grid(BaseModel):
    """What produced and corrected the simulated days."""

    model: str = Field(description="Global and regional models, scenario")
    reference: str = Field(description="What the correction was calibrated against")
    calibration_start: date = Field(description="Correction calibrated from")
    calibration_end: date
    projection_start: date = Field(description="Simulated days served from")
    projection_end: date
    step: float = Field(description="Grid spacing, degrees")
    temperature_step: float | None = Field(
        default=None, description="Grid spacing of the temperatures, when finer"
    )
    generated: date = Field(description="When the store was built")


class NormalDay(BaseModel):
    """The seasonal normal of one date: a mean over the reference period, not a day."""

    date: date
    temperature_min: float | None = Field(default=None, description="degrees Celsius")
    temperature_max: float | None = Field(default=None, description="degrees Celsius")
    precipitation: float | None = Field(default=None, description="millimetres per day")


class Normals(BaseModel):
    """The seasonal normals of a range, at the cells the range is read at."""

    reference_start: date
    reference_end: date
    window_days: int = Field(description="Width of the centred moving window, days")
    days: list[NormalDay]


class ClimateMonth(BaseModel):
    """One month of the climate diagram: means over the years of the window."""

    month: int = Field(description="1 to 12")
    temperature_mean: float | None = Field(default=None, description="degrees Celsius")
    temperature_min: float | None = Field(default=None, description="degrees Celsius")
    temperature_max: float | None = Field(default=None, description="degrees Celsius")
    precipitation: float | None = Field(default=None, description="millimetres per month")
    dry: bool | None = Field(default=None, description="P <= 2T (Bagnouls and Gaussen)")


class ClimateWindow(BaseModel):
    start_year: int
    end_year: int
    origin: Origin = Field(description="observed (ERA5) or simulated (corrected CORDEX)")
    source: str


class Climate(BaseModel):
    """The climate diagram of a place: the window around the year searched, and a
    reference period of the normals."""

    window: ClimateWindow
    months: list[ClimateMonth]
    reference: ClimateWindow
    reference_months: list[ClimateMonth]


class Series(BaseModel):
    """The answer to one search."""

    latitude: float = Field(description="Centre of the cell the temperatures are read at")
    longitude: float = Field(description="Centre of the cell the temperatures are read at")
    start: date
    end: date
    has_simulated: bool = Field(description="True when the days come from the climate model")
    humid_heat_peak: int = Field(default=0, description="Highest humid-heat level of the range")
    grid: Grid | None = Field(default=None, description="Null for ERA5 days")
    days: list[Day]


class YearSummary(BaseModel):
    """One year of the matrix: the dates of the search in that year."""

    year: int
    start: date
    end: date
    origin: Origin | None = Field(default=None, description="null when no source serves these dates")
    temperature_mean: float | None = Field(default=None, description="degrees Celsius, tas")
    temperature_anomaly: float | None = Field(default=None, description="degrees, to the reference")
    temperature_sigmas: float | None = Field(default=None, description="anomaly in standard deviations")
    temperature_class: str | None = Field(
        default=None, description="much_colder, colder, near, warmer, much_warmer")
    precipitation: float | None = Field(default=None, description="millimetres over the dates")
    precipitation_ratio: float | None = Field(default=None, description="to the reference mean")
    precipitation_class: str | None = Field(
        default=None, description="much_drier, drier, near, wetter, much_wetter")


class Years(BaseModel):
    """Every year from 1970 to 2100, beside a reference period of the normals."""

    reference_start: date
    reference_end: date
    temperature_normal: float = Field(description="mean of the reference years, degrees Celsius")
    temperature_sigma: float = Field(description="interannual standard deviation, degrees")
    precipitation_normal: float = Field(description="mean of the reference years, millimetres")
    years: list[YearSummary]


class SummaryFigure(BaseModel):
    """One figure of the summary, and its normal (mean over the reference years)."""

    value: float | None = None
    normal: float | None = None


class SeasonRank(BaseModel):
    """Where the dates shown stand among the same dates of every observed year
    (summary.rank): by the mean of the daily maximum, the year shown left out."""

    first: int = Field(description="first observed year compared")
    last: int = Field(description="last observed year compared")
    total: int = Field(description="observed years compared")
    warmer: int = Field(description="of them, those warmer than the dates shown")
    warmer_years: list[int] = Field(description="their years, when there are three at most")


class Summary(BaseModel):
    """The figures of the dates of a search beside the reference period (summary.py):
    tasmax_mean, tas_mean, hot_35, hot_40, tropical_nights, summer_days,
    frost_days, precipitation; and their rank among the observed years."""

    reference_start: date
    reference_end: date
    figures: dict[str, SummaryFigure]
    rank: SeasonRank | None = None


class Peak(BaseModel):
    """One day of an epoch: the hottest (tasmax) or the coldest night (tasmin)."""

    year: int = Field(description="the year of the season that holds the day")
    date: date
    value: float = Field(description="degrees Celsius")


class KindsEpoch(BaseModel):
    """The years of one epoch, sorted into cool, normal and warm seasons."""

    id: str
    first: int
    last: int
    origin: Origin | None = Field(description="null when the epoch mixes past data and simulation")
    cool: list[int]
    normal: list[int]
    warm: list[int]
    values: dict[int, float] = Field(description="mean tasmax of each year, degrees Celsius")
    hottest: Peak | None = Field(default=None, description="the day of the highest tasmax")
    coldest: Peak | None = Field(default=None, description="the night of the lowest tasmin")


class Kinds(BaseModel):
    """The epochs of the home form (kinds.EPOCHS), ranked at one place."""

    epochs: list[KindsEpoch]


class Place(BaseModel):
    """The town nearest a point of the map (places.py), or no name when none of
    the list is within places.MAX_KM."""

    name: str | None
    country: str | None
    distance_km: float | None
