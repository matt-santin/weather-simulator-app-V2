"""Snow on the ground (src.app.domain.snow) on made-up series, and its place in
the climate diagram on the small store of conftest.py."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.app.api import climate
from src.app.api.app import app, get_store
from src.app.domain import snow, thresholds
from src.app.store import Store

GRENOBLE = {"latitude": 45.18, "longitude": 5.72}
# No 0.1 deg cell there: the temperatures are the coarse ones, which start at 0 deg C
# every 3000 days (conftest.py), so snow settles now and then. The fine ones never freeze.
CORNER = {"latitude": 45.0, "longitude": 6.0}
HIGH = {"latitude": 46.0, "longitude": 6.0}
UNKNOWN = {"latitude": 46.0, "longitude": 5.9}


def series(start: date, end: date, tas: float = 10.0, pr: float = 0.0):
    n = (end - start).days + 1
    return np.full(n, tas), np.full(n, pr)


def at(start: date, day: date) -> int:
    return (day - start).days


def test_snow_falls_under_the_threshold_and_stays_while_it_freezes() -> None:
    start = date(2000, 8, 1)
    tas, pr = series(start, date(2001, 7, 31))
    cold = slice(at(start, date(2001, 1, 10)), at(start, date(2001, 1, 20)))
    tas[cold] = -2.0
    pr[at(start, date(2001, 1, 10))] = 5.0
    ground = snow.on_ground(tas, pr, start)
    # 5 mm fell on the 10th, nothing melts at -2: ten days, gone on the first mild one.
    assert ground.sum() == 10
    assert ground[cold].all()
    assert snow.per_winter(tas, pr, start) == {2001: 10}


def test_rain_above_the_threshold_adds_nothing() -> None:
    start = date(2000, 8, 1)
    tas, pr = series(start, date(2001, 7, 31), tas=thresholds.SNOW_FALL_C, pr=10.0)
    assert not snow.on_ground(tas, pr, start).any()


def test_each_degree_melts_its_share() -> None:
    start = date(2000, 8, 1)
    tas, pr = series(start, date(2001, 7, 31))
    k = at(start, date(2001, 2, 1))
    tas[k], pr[k] = -1.0, 12.0
    tas[k + 1:k + 10] = 1.0  # 4 mm a day: 8 mm left, then 4, then none
    ground = snow.on_ground(tas, pr, start)
    assert ground[k:k + 4].tolist() == [True, True, True, False]


def test_less_than_the_stock_is_not_snow_on_the_ground() -> None:
    start = date(2000, 8, 1)
    tas, pr = series(start, date(2001, 7, 31), tas=-5.0)
    pr[at(start, date(2001, 1, 1))] = thresholds.SNOW_STOCK_MM - 0.1
    assert not snow.on_ground(tas, pr, start).any()
    pr[at(start, date(2001, 1, 1))] = thresholds.SNOW_STOCK_MM
    assert snow.on_ground(tas, pr, start).any()


def test_the_stock_is_emptied_on_the_first_of_august() -> None:
    start = date(2000, 8, 1)
    tas, pr = series(start, date(2002, 7, 31), tas=-5.0)  # never melts
    pr[at(start, date(2001, 3, 1))] = 50.0
    ground = snow.on_ground(tas, pr, start)
    assert ground[at(start, date(2001, 7, 31))]
    assert not ground[at(start, date(2001, 8, 1))]


def test_days_are_counted_from_november_to_april_by_winter() -> None:
    start = date(2000, 8, 1)
    tas, pr = series(start, date(2002, 7, 31), tas=-5.0)
    pr[at(start, date(2000, 10, 1))] = 50.0  # on the ground from October to the end of July
    pr[at(start, date(2002, 4, 21))] = 50.0  # the last ten days of April
    assert snow.per_winter(tas, pr, start) == {2001: 181, 2002: 10}


def test_gaps_neither_add_nor_melt() -> None:
    start = date(2000, 8, 1)
    tas, pr = series(start, date(2001, 7, 31))
    k = at(start, date(2001, 1, 10))
    tas[k:k + 5] = -2.0
    pr[k] = 5.0
    tas[k + 2] = np.nan      # the stock is kept
    pr[k + 3] = np.nan       # nothing falls
    assert snow.on_ground(tas, pr, start)[k:k + 6].tolist() == [True] * 5 + [False]


@pytest.fixture
def store(store_path) -> Store:
    return Store(store_path)


@pytest.fixture
def client(store) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def brute(store: Store, source: str, cell, first: int, last: int) -> float:
    """Mean days per winter, winter by winter, each read on its own."""
    counts = []
    for year in range(first, last + 1):
        start = date(year - 1, 8, 1)
        if start < date(1970, 1, 1):
            continue
        values = store.values(source, cell, start, date(year, 4, 30), ("tas", "pr"))
        counts.append(snow.per_winter(values["tas"], values["pr"], start)[year])
    return sum(counts) / len(counts)


def test_a_past_window_is_counted_on_the_past_data(client: TestClient, store: Store) -> None:
    answer = client.get("/api/climate", params={**CORNER, "start": "1985-01-01", "end": "1985-01-31"}).json()
    cell = store.cell(**CORNER)
    own, reference = answer["snow"], answer["reference_snow"]
    assert own["days"] > 0 and reference["days"] > 0
    assert own["days"] == pytest.approx(brute(store, "era5", cell, 1978, 1992), abs=0.051)
    assert (own["winters"], own["rare"], own["baseline_start_year"]) == (15, False, None)
    assert reference["days"] == pytest.approx(brute(store, "era5", cell, 1991, 2020), abs=0.051)
    assert reference["winters"] == 30


def test_the_first_window_has_no_winter_1970(client: TestClient) -> None:
    answer = client.get("/api/climate", params={**GRENOBLE, "start": "1972-01-01", "end": "1972-01-31"}).json()
    assert answer["window"]["start_year"] == 1970
    assert answer["snow"]["winters"] == 14


def test_a_simulated_window_is_the_past_count_times_the_change_of_the_model(
        client: TestClient, store: Store, monkeypatch) -> None:
    monkeypatch.setattr(thresholds, "SNOW_RARE_DAYS", 0.1)
    answer = client.get("/api/climate", params={**CORNER, "start": "2084-06-21", "end": "2084-09-20",
                                                "reference": 1971}).json()
    cell = store.cell(**CORNER)
    past = brute(store, "era5", cell, 1991, 2020)
    model = brute(store, "cordex", cell, 1991, 2020)
    future = brute(store, "cordex", cell, 2077, 2091)
    assert model >= thresholds.SNOW_RARE_DAYS and future > 0 and past > 0
    own = answer["snow"]
    assert own["days"] == pytest.approx(past * future / model, abs=0.051)
    # The baseline is 1991-2020 whatever the reference drawn in grey.
    assert (own["baseline_start_year"], own["baseline_end_year"]) == (1991, 2020)
    assert answer["reference_snow"]["days"] == pytest.approx(brute(store, "era5", cell, 1971, 2000), abs=0.051)


def test_too_little_snow_in_the_model_gives_no_number(store: Store, monkeypatch) -> None:
    monkeypatch.setattr(thresholds, "SNOW_RARE_DAYS", 1000.0)
    period, first, last = climate.window(2084)
    own, reference = climate.snows(store, store.cell(**GRENOBLE), period, first, last, 1991, 2020)
    assert own.rare and own.days is None and own.baseline_start_year == 1991
    assert reference.days is not None and not reference.rare


@pytest.mark.parametrize("where", [HIGH, UNKNOWN])
def test_no_snow_above_the_gate_or_without_altitude(client: TestClient, where: dict) -> None:
    answer = client.get("/api/climate", params={**where, "start": "2084-06-21", "end": "2084-09-20"}).json()
    assert answer["snow"] is None and answer["reference_snow"] is None
    assert len(answer["months"]) == 12

