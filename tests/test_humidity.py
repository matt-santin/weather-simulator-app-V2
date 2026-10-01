"""The wet bulb, and the level a card turns on.

Two things are worth checking: that the fit is Stull's and close to exact
psychrometry where the levels sit, and that the levels fall where thresholds.py
says, before any rounding.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from src.app.api.contract import Day
from src.app.domain import thresholds
from src.app.domain.humidity import humid_heat, wet_bulb
from src.app.domain.records import DailyRecord, Origin


def psychrometric(temperature: float, humidity: float, pressure: float = 1013.25) -> float:
    """The exact wet bulb, solved rather than fitted, as an independent yardstick.

    Deliberately not the implementation under test: Stull is an empirical fit
    found by gene-expression programming, and comparing it to itself would check
    nothing. This solves es(Tw) - A p (T - Tw) = e by bisection, A being the
    psychrometer constant of a ventilated thermometer.
    """

    def es(value: float) -> float:
        return 6.112 * math.exp(17.62 * value / (243.12 + value))

    target, low, high = es(temperature) * humidity / 100.0, -60.0, temperature
    for _ in range(80):
        middle = (low + high) / 2
        if es(middle) - 6.53e-4 * pressure * (temperature - middle) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def test_the_fit_reproduces_the_published_table() -> None:
    """32 °C at 90 % is 30.6 °C of wet bulb, which is a cell of the matrix."""
    assert wet_bulb(32.0, 90.0) == pytest.approx(30.6, abs=0.05)


@pytest.mark.parametrize(
    ("temperature", "humidity"),
    [(30.0, 70.0), (32.0, 85.0), (35.0, 70.0), (36.0, 90.0), (40.0, 60.0)],
)
def test_the_fit_and_the_exact_solution_agree_where_the_levels_sit(
    temperature: float, humidity: float
) -> None:
    """Under half a degree apart on the humid quadrant, which is the claim made.

    Stull costs -1.0 to +0.65 °C over its whole validated range, and the module
    docstring asserts that the cost lands away from the thresholds. This is that
    assertion, checked: on the columns where a level can fire, the fit and the
    exact solution are close enough that the choice between them changes no card.
    """
    assert wet_bulb(temperature, humidity) == pytest.approx(
        psychrometric(temperature, humidity), abs=0.5
    )


def test_saturation_is_the_air_temperature_and_never_above_it() -> None:
    """A fit can exceed the air temperature at saturation, which is unphysical,
    and a foggy day is exactly where the level is closest to firing. A humidity
    above 100 % is capped rather than refused."""
    assert wet_bulb(28.0, 100.0) == pytest.approx(28.0, abs=0.05)
    assert wet_bulb(12.0, 104.0) <= 12.0


def test_a_missing_input_gives_no_reading_rather_than_a_guess() -> None:
    """A gap travels; it is not filled. Same rule as the sky class."""
    assert wet_bulb(None, 20.0) is None
    assert wet_bulb(25.0, None) is None
    assert humid_heat(None) is None


def test_the_levels_fall_where_the_thresholds_say() -> None:
    """Zero is an answer, null is the absence of one, and both reach the card."""
    assert humid_heat(0.0) == 0
    assert humid_heat(thresholds.HUMID_HEAT_C - 0.01) == 0
    assert humid_heat(thresholds.HUMID_HEAT_C) == 1
    assert humid_heat(thresholds.HUMID_HEAT_EXTREME_C - 0.01) == 1
    assert humid_heat(thresholds.HUMID_HEAT_EXTREME_C) == 2


def test_the_level_is_read_before_the_tenth_is_taken() -> None:
    """A day at 25.97 must not become level 1 by being tidied up.

    The same order ``cloud_cover`` obeys, and it has teeth here: the rounded
    value the card ships reads 26.0, which is the threshold, while the level it
    ships is 0. Rounding first would flip it, and the two fields would then
    contradict each other on screen.
    """
    day = Day.from_record(
        DailyRecord(
            date=date(2046, 7, 14),
            origin=Origin.SIMULATED,
            source="test",
            temperature_mean=26.52,
            relative_humidity_mean=95.7,
        ),
        sky=None,
    )
    assert day.wet_bulb_mean == pytest.approx(26.0)
    assert day.humid_heat == 0
