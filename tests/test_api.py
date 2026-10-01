"""The two endpoints, on the small store of conftest.py."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from conftest import GAP, expected
from src.app.api.app import app, get_store
from src.app.store import Store

GRENOBLE = {"latitude": 45.18, "longitude": 5.72}


@pytest.fixture
def client(store_path) -> TestClient:
    store = Store(store_path)
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def days(client: TestClient, start: str, end: str, where: dict = GRENOBLE):
    return client.get("/api/days", params={**where, "start": start, "end": end})


def test_config_serves_the_two_periods(client: TestClient) -> None:
    config = client.get("/api/config").json()
    assert config["coverage_start"] == "1970-01-01"
    assert config["coverage_end"] == "2100-12-31"
    assert config["periods"] == [
        {"start": "1970-01-01", "end": "2005-12-31", "origin": "observed"},
        {"start": "2027-01-01", "end": "2100-12-31", "origin": "simulated"},
    ]
    assert config["max_days"] == 92


def test_a_past_range_is_era5_and_carries_no_warning(client: TestClient) -> None:
    response = days(client, "1985-01-01", "1985-01-31")
    assert response.status_code == 200
    series = response.json()
    assert series["has_simulated"] is False
    assert series["grid"] is None
    assert len(series["days"]) == 31
    assert {d["origin"] for d in series["days"]} == {"observed"}
    assert {d["source"] for d in series["days"]} == {"ERA5"}


def test_a_future_range_is_cordex_and_says_so(client: TestClient) -> None:
    series = days(client, "2044-06-21", "2044-09-20").json()
    assert series["has_simulated"] is True
    assert {d["origin"] for d in series["days"]} == {"simulated"}
    assert series["grid"]["projection_start"] == "2027-01-01"
    assert series["grid"]["step"] == 0.25
    assert series["grid"]["generated"] == "2026-09-30"
    assert len(series["days"]) == 92


def test_each_day_is_read_at_its_own_date(client: TestClient) -> None:
    """The small store holds the day index: a shift of one day would show."""
    for source, start in (("era5", date(1999, 12, 30)), ("cordex", date(2080, 2, 28))):
        served = days(client, start.isoformat(), start.replace(day=start.day + 1).isoformat())
        first = served.json()["days"][0]
        assert first["date"] == start.isoformat()
        assert first["temperature_max"] == pytest.approx(round(expected(source, start, "tasmax"), 1))


def test_the_wind_is_served_in_kmh(client: TestClient) -> None:
    day = date(2044, 7, 1)
    served = days(client, day.isoformat(), day.isoformat()).json()["days"][0]
    assert served["wind_speed_mean"] == pytest.approx(round(expected("cordex", day, "sfcWind") * 3.6, 1))


def test_a_gap_stays_a_gap(client: TestClient) -> None:
    served = days(client, GAP.isoformat(), GAP.isoformat()).json()["days"][0]
    assert served["precipitation"] is None
    assert served["sky"] is None
    assert served["temperature_max"] is not None


def test_the_nearest_cell_is_served(client: TestClient) -> None:
    series = days(client, "2044-07-01", "2044-07-02").json()
    assert (series["latitude"], series["longitude"]) == (45.25, 5.75)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2015-07-01", "2015-07-14"),  # between the two periods
        ("2005-12-15", "2006-01-10"),  # straddling the end of ERA5
        ("2026-12-20", "2027-01-10"),  # straddling the start of CORDEX
        ("1969-12-20", "1970-01-10"),  # before the first
        ("2100-12-20", "2101-01-10"),  # after the last
    ],
)
def test_a_range_outside_one_period_is_refused_whole(client: TestClient, start, end) -> None:
    response = days(client, start, end)
    assert response.status_code == 400
    message = response.json()["message"]
    assert message.startswith("Données indisponibles")
    assert "1970-2005 et 2027-2100" in message


def test_more_than_a_season_is_refused(client: TestClient) -> None:
    response = days(client, "2044-06-01", "2044-09-01")
    assert response.status_code == 400
    assert "92 jours" in response.json()["message"]


def test_a_backward_range_is_refused(client: TestClient) -> None:
    response = days(client, "2044-07-10", "2044-07-01")
    assert response.status_code == 400
    assert "précède" in response.json()["message"]


@pytest.mark.parametrize(
    "where",
    [
        {"latitude": 46.0, "longitude": 5.0},  # a cell outside the domain
        {"latitude": 10.0, "longitude": 5.0},  # off the grid
    ],
)
def test_a_place_outside_the_domain_is_refused(client: TestClient, where) -> None:
    response = days(client, "2044-07-01", "2044-07-14", where)
    assert response.status_code == 400
    assert response.json()["message"] == "Lieu hors de la zone couverte (Europe)."


def test_a_malformed_search_gets_one_sentence(client: TestClient) -> None:
    response = client.get("/api/days", params={"latitude": "x", "longitude": 5, "start": "2044-07-01"})
    assert response.status_code == 422
    assert response.json()["message"].startswith("Recherche invalide")
