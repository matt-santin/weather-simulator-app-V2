"""The Köppen-Geiger classes, on the criteria of Beck et al. 2023 (src.app.domain.koppen)."""

from __future__ import annotations

import numpy as np

from src.app.domain.koppen import classify, of_place

# Twelve months, January first: rounded climates of the kind each class names.
PARIS_T = [5, 6, 9, 12, 16, 19, 21, 21, 18, 13, 8, 5]
PARIS_P = [50, 40, 48, 52, 63, 50, 62, 52, 48, 62, 52, 58]
SEVILLE_T = [11, 12, 15, 17, 21, 25, 28, 28, 25, 20, 15, 12]
SEVILLE_P = [60, 55, 45, 50, 30, 10, 2, 5, 25, 60, 80, 90]
MOSCOW_T = [-8, -6, -1, 6, 12, 16, 18, 17, 12, 6, 0, -5]
MOSCOW_P = [40, 35, 40, 45, 60, 80, 90, 80, 60, 55, 50, 45]


def test_three_familiar_climates() -> None:
    assert of_place(PARIS_T, PARIS_P) == "Cfb"
    assert of_place(SEVILLE_T, SEVILLE_P) == "Csa"
    assert of_place(MOSCOW_T, MOSCOW_P) == "Dfb"


def test_a_warmer_summer_turns_b_into_a() -> None:
    """Thot >= 22 degC: the third letter is a."""
    hot = [t + 2 for t in PARIS_T]
    assert of_place(hot, PARIS_P) == "Cfa"


def test_temperate_and_cold_are_split_at_zero() -> None:
    """C needs a coldest month above 0 degC, not -3 as in Köppen's own scheme."""
    at_minus_one = [-1, 1, 5, 10, 15, 19, 21, 20, 16, 11, 5, 1]
    assert of_place(at_minus_one, PARIS_P)[0] == "D"
    assert of_place([t + 1.5 for t in at_minus_one], PARIS_P)[0] == "C"


def test_arid_wins_over_the_temperature_classes() -> None:
    """Too little rain for the warmth: B, whatever the temperatures say."""
    assert of_place(SEVILLE_T, [p / 4 for p in SEVILLE_P]) == "BWh"
    assert of_place(SEVILLE_T, [p / 2 for p in SEVILLE_P]) == "BSh"
    assert of_place(MOSCOW_T, [p / 4 for p in MOSCOW_P]) == "BSk"


def test_dry_summer_and_dry_winter_exclude_each_other() -> None:
    """s only when winter is the wetter half, w only when summer is."""
    monsoon = [10, 12, 16, 20, 23, 25, 26, 26, 24, 20, 15, 11]
    wet_summer = [2, 3, 6, 20, 60, 150, 200, 180, 90, 20, 5, 2]
    assert of_place(monsoon, wet_summer) == "Cwa"
    assert of_place(SEVILLE_T, SEVILLE_P)[1] == "s"


def test_polar_and_tropical() -> None:
    assert of_place([-20, -20, -18, -12, -4, 2, 6, 5, 1, -6, -13, -18], [20] * 12) == "ET"
    assert of_place([26] * 12, [200] * 12) == "Af"


def test_a_missing_month_gives_nothing() -> None:
    assert of_place(PARIS_T[:11] + [None], PARIS_P) is None
    T = np.array([PARIS_T, SEVILLE_T], dtype=float).T
    T[3, 1] = np.nan
    assert list(classify(T, np.array([PARIS_P, SEVILLE_P], dtype=float).T)) == ["Cfb", ""]
