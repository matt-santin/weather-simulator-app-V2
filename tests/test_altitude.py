"""Temperatures brought to the altitude of the place (src.app.domain.altitude),
on the small store of conftest.py: every 0.1 deg cell stands at 300 m."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from fastapi.testclient import TestClient

from conftest import expected
from src.app.api.app import app, get_store
from src.app.domain import altitude
from src.app.store import Store

GRENOBLE = {"latitude": 45.18, "longitude": 5.72}
FALLBACK = {"latitude": 45.5, "longitude": 5.5}   # 0.1 deg cell served from ERA5-Land
CORNER = {"latitude": 45.0, "longitude": 6.0}     # no 0.1 deg cell
HIGH = {"latitude": 46.0, "longitude": 6.0}       # cell at 1 500 m
UNKNOWN = {"latitude": 46.0, "longitude": 5.9}    # cell of unknown altitude


@pytest.fixture
def store(store_path) -> Store:
    return Store(store_path)


@pytest.fixture
def client(store) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_a_cell_above_its_place_is_warmed_by_the_rate_of_the_month() -> None:
    shift = altitude.shift("tasmax", date(2001, 1, 31), 2, 1000.0)
    assert shift.tolist() == [3.9, 5.7]  # 31 January, 1 February
    assert altitude.shift("tasmin", date(2001, 7, 1), 1, -500.0).tolist() == [-2.0]
    # The daily mean takes the mean of the two rates.
    assert altitude.shift("tas", date(2001, 7, 1), 1, 1000.0)[0] == pytest.approx((4.0 + 7.8) / 2)


def test_the_gap_is_cut() -> None:
    assert altitude.lift(300.0, 5000.0) == -altitude.MAX_LIFT_M
    assert altitude.lift(2456.0, 1035.0) == 1421.0


def test_only_an_eobs_cell_of_known_altitude_is_corrected(store: Store) -> None:
    assert store.cell(**GRENOBLE).lift is None
    assert store.cell(**GRENOBLE, elevation=100.0).lift == 200.0
    for where in (FALLBACK, CORNER, UNKNOWN):
        assert store.cell(**where, elevation=100.0).lift is None


def test_the_days_are_served_at_the_altitude_of_the_place(client: TestClient) -> None:
    params = {**GRENOBLE, "start": "1985-01-30", "end": "1985-02-02"}
    plain = client.get("/api/days", params=params).json()
    moved = client.get("/api/days", params={**params, "elevation": 100}).json()
    assert (plain["place_elevation"], plain["cell_elevation"]) == (None, 300)
    assert (moved["place_elevation"], moved["cell_elevation"]) == (100, 300)
    # 200 m: 3.9 K/km in January, 5.7 in February on the maximum; 2.4 and 3.3 on the minimum.
    for day, a, b in zip(("1985-01-30", "1985-01-31", "1985-02-01", "1985-02-02"), plain["days"], moved["days"]):
        january = day < "1985-02"
        assert b["temperature_max"] - a["temperature_max"] == pytest.approx(0.78 if january else 1.14, abs=0.051)
        assert b["temperature_min"] - a["temperature_min"] == pytest.approx(0.48 if january else 0.66, abs=0.051)
        assert a["temperature_max"] == pytest.approx(expected("era5", date.fromisoformat(day), "tasmax", fine=True), abs=0.051)
        assert b["precipitation"] == a["precipitation"]


def test_past_and_simulated_days_move_alike(store: Store) -> None:
    plain, moved = store.cell(**GRENOBLE), store.cell(**GRENOBLE, elevation=800.0)
    for source in ("era5", "cordex"):
        a = store.values(source, plain, date(2001, 7, 1), date(2001, 7, 3), ("tasmax", "tas", "pr"))
        b = store.values(source, moved, date(2001, 7, 1), date(2001, 7, 3), ("tasmax", "tas", "pr"))
        assert np.allclose(b["tasmax"] - a["tasmax"], -7.8 * 0.5)
        assert np.allclose(b["tas"] - a["tas"], -5.9 * 0.5)
        assert np.array_equal(b["pr"], a["pr"])


def test_every_call_of_a_search_takes_the_altitude(client: TestClient) -> None:
    params = {**GRENOBLE, "start": "2084-06-21", "end": "2084-09-20"}
    for path, read in (
        ("/api/normals", lambda a: a["days"][0]["temperature_max"]),
        ("/api/climate", lambda a: a["months"][6]["temperature_max"]),
        ("/api/years", lambda a: a["temperature_normal"]),
        ("/api/summary", lambda a: a["figures"]["tasmax_mean"]["value"]),
    ):
        plain = client.get(path, params=params)
        moved = client.get(path, params={**params, "elevation": 1300})
        assert plain.status_code == moved.status_code == 200, path
        assert read(moved.json()) < read(plain.json()) - 2, path
    assert client.get("/api/kinds", params={**params, "elevation": 1300}).status_code == 200
    plain = client.get("/api/card.png", params=params)
    moved = client.get("/api/card.png", params={**params, "elevation": 1300})
    assert moved.status_code == 200 and moved.content != plain.content


def test_an_altitude_that_is_not_one_is_refused_by_the_api(client: TestClient) -> None:
    params = {**GRENOBLE, "start": "1985-01-01", "end": "1985-01-31"}
    assert client.get("/api/days", params={**params, "elevation": 9000}).status_code != 200
    assert client.get("/api/days", params={**params, "elevation": "haut"}).status_code != 200


def test_the_snow_gate_is_for_places_left_at_the_altitude_of_their_cell(client: TestClient) -> None:
    params = {**HIGH, "start": "1985-01-01", "end": "1985-01-31"}
    assert client.get("/api/climate", params=params).json()["snow"] is None
    assert client.get("/api/climate", params={**params, "elevation": 1400}).json()["snow"] is not None
    # No correction without a known altitude of the cell: the gate stays.
    unknown = {**UNKNOWN, "start": "1985-01-01", "end": "1985-01-31", "elevation": 1400}
    assert client.get("/api/climate", params=unknown).json()["snow"] is None


def test_the_preview_of_a_shared_search_carries_the_altitude(client: TestClient) -> None:
    address = {"lieu": "Grenoble", "lat": 45.18, "lon": 5.72, "debut": "2063-06-21", "fin": "2063-09-20"}
    page = client.get("/resultats", params={**address, "alt": "212"}).text
    assert "api/card.png?" in page and "elevation=212" in page
    # An altitude that is not one is left out: the page is still that of the search.
    for alt in ("", "haut", "99999"):
        page = client.get("/resultats", params={**address, "alt": alt}).text
        assert "api/card.png?" in page and "elevation" not in page.split("</head>")[0]
