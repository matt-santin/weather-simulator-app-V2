"""The sky class, at its boundaries and on the days it must refuse to classify."""

from __future__ import annotations

from datetime import date

import pytest

from src.app.domain import thresholds
from src.app.domain.records import DailyRecord, Origin
from src.app.domain.sky import SkyClass, classify, classify_record

WET = thresholds.PRECIPITATION_MM
COLD = thresholds.SNOW_TEMPERATURE_C
OVERCAST = thresholds.OVERCAST_PERCENT
CLOUDY = thresholds.CLOUDY_PERCENT


@pytest.mark.parametrize(
    ("precipitation", "temperature", "cloud", "expected"),
    [
        (0.0, 10.0, 0.0, SkyClass.CLEAR),
        (0.0, 10.0, CLOUDY - 0.1, SkyClass.CLEAR),
        (0.0, 10.0, CLOUDY, SkyClass.CLOUDY),
        (0.0, 10.0, OVERCAST - 0.1, SkyClass.CLOUDY),
        (0.0, 10.0, OVERCAST, SkyClass.OVERCAST),
        (0.0, 10.0, 100.0, SkyClass.OVERCAST),
        (WET, 10.0, 0.0, SkyClass.RAIN),
        (WET, COLD - 0.1, 0.0, SkyClass.SNOW),
        (WET, COLD, 0.0, SkyClass.RAIN),
        (50.0, -20.0, 100.0, SkyClass.SNOW),
    ],
)
def test_the_thresholds_are_inclusive_from_below(
    precipitation: float, temperature: float, cloud: float, expected: SkyClass
) -> None:
    """Each threshold belongs to the class above it, and the day just under does not."""
    assert classify(precipitation, temperature, cloud) is expected


def test_a_wet_day_never_reads_the_sky() -> None:
    """Rain and snow win outright: cloud cover cannot overturn them, nor rescue them."""
    assert classify(WET, 10.0, 0.0) is SkyClass.RAIN
    assert classify(WET, 10.0, 100.0) is SkyClass.RAIN
    # And a wet day with no cloud figure at all is still classifiable.
    assert classify(WET, -5.0, None) is SkyClass.SNOW


def test_a_dry_day_just_below_the_gate_is_dry() -> None:
    """The gate is shared by the snow and rain rules, so they partition the same days."""
    assert classify(WET - 0.001, -20.0, 0.0) is SkyClass.CLEAR


def test_a_missing_value_gives_no_class() -> None:
    """A gap is a gap. Substituting a class would be a data-treatment decision."""
    assert classify(None, 10.0, 50.0) is None
    assert classify(0.0, 10.0, None) is None
    # Temperature is only needed once the wet gate is crossed.
    assert classify(WET, None, 50.0) is None
    assert classify(0.0, None, 50.0) is SkyClass.CLOUDY


def test_the_record_and_the_values_agree() -> None:
    """The two entry points are one rule, not two."""
    record = DailyRecord(
        date=date(2046, 7, 14),
        origin=Origin.SIMULATED,
        precipitation=0.0,
        temperature_mean=24.0,
        cloud_cover=OVERCAST + 5,
    )
    assert classify_record(record) is SkyClass.OVERCAST
    assert classify_record(record) is classify(
        record.precipitation, record.temperature_mean, record.cloud_cover
    )


def test_an_empty_record_gives_no_class() -> None:
    record = DailyRecord(date=date(1950, 1, 1), origin=Origin.OBSERVED)
    assert classify_record(record) is None


def test_the_class_travels_as_a_word_not_a_pictogram() -> None:
    """Section 4 keeps the emoji on the display side; the contract carries the class."""
    assert SkyClass.OVERCAST == "overcast"
    assert {c.value for c in SkyClass} == {"clear", "cloudy", "overcast", "rain", "snow"}
