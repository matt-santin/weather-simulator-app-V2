"""The temperature band: nine steps, and what falls either side of a line.

The boundaries themselves are a convention over a continuum, so nothing here
argues for five degrees — scripts/temperature_scale/ does that. What is pinned is
that the rule is total, monotone, and identical whatever served the day.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.app.domain import thresholds
from src.app.domain.records import DailyRecord, Origin
from src.app.domain.temperature import BAND_COUNT, band, bands_of


def test_the_scale_has_nine_steps() -> None:
    """One per colour the palette can name."""
    assert BAND_COUNT == 9
    assert len(thresholds.TEMPERATURE_BAND_EDGES) == 8


@pytest.mark.parametrize(
    ("temperature", "expected"),
    [
        (-40.0, 0),  # nothing falls off the cold end
        (4.9, 0),
        (5.0, 1),  # a value on an edge takes the warmer band
        (10.0, 2),
        (15.0, 3),
        (20.0, 4),
        (25.0, 5),
        (30.0, 6),
        (35.0, 7),
        (39.9, 7),
        (40.0, 8),
        (55.0, 8),  # nor off the hot end
    ],
)
def test_where_each_temperature_falls(temperature: float, expected: int) -> None:
    assert band(temperature) == expected


def test_the_scale_never_runs_out() -> None:
    """Total by construction: every step of a tenth of a degree lands somewhere."""
    seen = {band(-60 + tenth / 10) for tenth in range(1200)}
    assert seen == set(range(BAND_COUNT))


def test_the_scale_only_ever_climbs() -> None:
    previous = 0
    for tenth in range(1200):
        current = band(-60 + tenth / 10)
        assert current >= previous
        previous = current


def test_a_gap_gets_no_band() -> None:
    """No colour invented for a temperature that was never served."""
    assert band(None) is None


def test_a_day_is_read_minimum_first() -> None:
    record = DailyRecord(
        date=date(2046, 7, 14),
        origin=Origin.SIMULATED,
        source="MRI_AGCM3_2_S",
        temperature_min=19.0,
        temperature_max=32.0,
    )
    assert bands_of(record) == (band(19.0), band(32.0))
    assert bands_of(record) == (3, 6)


def test_the_two_temperatures_share_one_scale() -> None:
    """The same reading gets the same band, whichever of the two it is.

    It is what makes the two numbers on a card comparable, and it is also why the
    minimum lives in the cold half of the ramp.
    """
    warm_night = DailyRecord(
        date=date(2046, 7, 14),
        origin=Origin.SIMULATED,
        source="MRI_AGCM3_2_S",
        temperature_min=22.0,
        temperature_max=22.0,
    )
    low, high = bands_of(warm_night)
    assert low == high
