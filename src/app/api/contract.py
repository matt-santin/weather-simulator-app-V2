"""The JSON contract: one object per day, and what travels alongside them.

Kept from V1, so that the interface reads it unchanged, with three differences:
no ``wind_speed_max`` (CORDEX serves the daily mean wind only), no forecast
origin, and ``grid`` now describes the CORDEX correction rather than V1's
cloud-cover table.

It carries the sky class, never the pictogram; the temperature band, never the
colour; ``origin`` on every day and ``has_simulated`` on the response, which
the warning turns on. It omits ``temperature_mean`` and the relative humidity:
inputs of the snow criterion and the wet bulb, not displayed.
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
            temperature_min=_round(record.temperature_min),
            temperature_max=_round(record.temperature_max),
            precipitation=_round(record.precipitation),
            cloud_cover=_round(record.cloud_cover),
            wind_speed_mean=_round(record.wind_speed_mean),
            wet_bulb_mean=_round(wet_bulb),
            humid_heat=humidity.humid_heat(wet_bulb),
            sky=sky,
            temperature_min_band=low_band,
            temperature_max_band=high_band,
        )


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


class Grid(BaseModel):
    """What produced and corrected the simulated days."""

    model: str = Field(description="Global and regional models, scenario")
    reference: str = Field(description="What the correction was calibrated against")
    calibration_start: date = Field(description="Correction calibrated against ERA5 from")
    calibration_end: date
    projection_start: date = Field(description="Simulated days served from")
    projection_end: date
    step: float = Field(description="Grid spacing, degrees")
    temperature_step: float | None = Field(
        default=None, description="Grid spacing of the temperatures, when finer"
    )
    generated: date = Field(description="When the store was built")


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
