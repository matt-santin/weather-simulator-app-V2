"""The two endpoints, on the small store of conftest.py."""

from __future__ import annotations

from datetime import date, timedelta

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
        {"start": "1970-01-01", "end": "2025-12-31", "origin": "observed"},
        {"start": "2027-01-01", "end": "2100-12-31", "origin": "simulated"},
    ]
    assert config["max_days"] == 92
    assert config["normals"] == [
        {"first": 1971, "label": "1971-2000"},
        {"first": 1981, "label": "1981-2010"},
        {"first": 1991, "label": "1991-2020"},
    ]
    assert config["normals_default"] == 1991


def test_a_past_range_is_era5_and_carries_no_warning(client: TestClient) -> None:
    response = days(client, "1985-01-01", "1985-01-31")
    assert response.status_code == 200
    series = response.json()
    assert series["has_simulated"] is False
    assert series["grid"] is None
    assert len(series["days"]) == 31
    assert {d["origin"] for d in series["days"]} == {"observed"}
    assert {d["source"] for d in series["days"]} == {"ERA5-Land (températures), ERA5"}


def test_a_future_range_is_cordex_and_says_so(client: TestClient) -> None:
    series = days(client, "2044-06-21", "2044-09-20").json()
    assert series["has_simulated"] is True
    assert {d["origin"] for d in series["days"]} == {"simulated"}
    assert series["grid"]["projection_start"] == "2027-01-01"
    assert series["grid"]["step"] == 0.25
    assert series["grid"]["temperature_step"] == 0.1
    assert series["grid"]["reference"] == "ERA5-Land (températures), ERA5"
    assert series["grid"]["generated"] == "2026-10-02"
    assert len(series["days"]) == 92


def test_each_day_is_read_at_its_own_date(client: TestClient) -> None:
    """The small store holds the day index: a shift of one day would show."""
    for source, start in (("era5", date(1999, 12, 30)), ("cordex", date(2080, 2, 28))):
        served = days(client, start.isoformat(), start.replace(day=start.day + 1).isoformat())
        first = served.json()["days"][0]
        assert first["date"] == start.isoformat()
        assert first["temperature_max"] == pytest.approx(round(expected(source, start, "tasmax", fine=True), 1))
        assert first["precipitation"] == pytest.approx(round(expected(source, start, "pr"), 1))


def test_the_wind_is_served_in_kmh(client: TestClient) -> None:
    day = date(2044, 7, 1)
    served = days(client, day.isoformat(), day.isoformat()).json()["days"][0]
    assert served["wind_speed_mean"] == pytest.approx(round(expected("cordex", day, "sfcWind") * 3.6, 1))


def test_a_gap_stays_a_gap(client: TestClient) -> None:
    served = days(client, GAP.isoformat(), GAP.isoformat()).json()["days"][0]
    assert served["precipitation"] is None
    assert served["sky"] is None
    assert served["temperature_max"] is not None


def test_the_temperatures_come_from_the_nearest_fine_cell(client: TestClient) -> None:
    series = days(client, "2044-07-01", "2044-07-02").json()
    assert (series["latitude"], series["longitude"]) == (45.2, 5.7)


def test_a_place_without_a_fine_cell_is_served_at_025(client: TestClient) -> None:
    day = date(2044, 7, 1)
    where = {"latitude": 45.0, "longitude": 6.0}
    series = days(client, day.isoformat(), day.isoformat(), where).json()
    assert (series["latitude"], series["longitude"]) == (45.0, 6.0)
    assert series["grid"]["temperature_step"] is None
    assert series["grid"]["reference"] == "ERA5"
    served = series["days"][0]
    assert served["source"] == "CORDEX EUR-11 corrigé"
    assert served["temperature_max"] == pytest.approx(round(expected("cordex", day, "tasmax"), 1))


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-07-01", "2026-07-14"),  # between the two periods
        ("2025-12-15", "2026-01-10"),  # straddling the end of ERA5
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
    assert "1970-2025 et 2027-2100" in message


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


def brute_normal(target: date, name: str, fine: bool, first: int = 1991) -> float:
    """Every day of the 30 years from `first` within 7 calendar days of the target's month and day,
    across the new year, averaged: the definition, without the server's arithmetic."""
    key = (date(2000, target.month, target.day) - date(2000, 1, 1)).days
    values = []
    day = date(first, 1, 1)
    while day <= date(first + 29, 12, 31):
        other = (date(2000, day.month, day.day) - date(2000, 1, 1)).days
        if min(abs(other - key), 366 - abs(other - key)) <= 7:
            values.append(expected("era5", day, name, fine=fine))
        day += timedelta(days=1)
    return sum(values) / len(values)


@pytest.mark.parametrize(("start", "end"), [("2044-06-21", "2044-06-23"), ("1999-12-30", "2000-01-02"),
                                            ("2048-02-28", "2048-03-01")])
def test_the_normals_are_the_1991_2020_mean_over_15_days(client: TestClient, start, end) -> None:
    response = client.get("/api/normals", params={**GRENOBLE, "start": start, "end": end})
    assert response.status_code == 200
    answer = response.json()
    assert (answer["reference_start"], answer["reference_end"]) == ("1991-01-01", "2020-12-31")
    assert answer["window_days"] == 15
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    assert [d["date"] for d in answer["days"]] == [
        (first + timedelta(days=k)).isoformat() for k in range((last - first).days + 1)]
    for served in answer["days"]:
        day = date.fromisoformat(served["date"])
        # Temperatures from the 0.1 deg cell, rain from the 0.25 deg one, always ERA5.
        assert served["temperature_max"] == pytest.approx(brute_normal(day, "tasmax", True), abs=0.051)
        assert served["temperature_min"] == pytest.approx(brute_normal(day, "tasmin", True), abs=0.051)
        assert served["precipitation"] == pytest.approx(brute_normal(day, "pr", False), abs=0.006)


def test_the_normals_follow_the_rules_of_a_search(client: TestClient) -> None:
    outside = client.get("/api/normals", params={"latitude": 46.0, "longitude": 5.0,
                                                 "start": "2044-06-21", "end": "2044-06-23"})
    assert outside.status_code == days(client, "2044-06-21", "2044-06-23",
                                       {"latitude": 46.0, "longitude": 5.0}).status_code != 200
    unavailable = client.get("/api/normals", params={**GRENOBLE, "start": "2026-06-21", "end": "2026-06-23"})
    assert unavailable.status_code != 200


@pytest.mark.parametrize("first", [1971, 1981])
def test_the_normals_may_be_an_older_30_years(client: TestClient, first) -> None:
    answer = client.get("/api/normals", params={**GRENOBLE, "start": "2044-07-14", "end": "2044-07-15",
                                                "reference": first}).json()
    assert (answer["reference_start"], answer["reference_end"]) == (f"{first}-01-01", f"{first + 29}-12-31")
    served = answer["days"][0]
    assert served["temperature_max"] == pytest.approx(brute_normal(date(2044, 7, 14), "tasmax", True, first),
                                                      abs=0.006)
    assert served["precipitation"] == pytest.approx(brute_normal(date(2044, 7, 14), "pr", False, first),
                                                    abs=0.006)


def test_an_unknown_reference_period_is_refused(client: TestClient) -> None:
    response = client.get("/api/normals", params={**GRENOBLE, "start": "2044-07-14", "end": "2044-07-15",
                                                  "reference": 1961})
    assert response.status_code == 400
    assert response.json()["message"] == ("Période de référence inconnue. Les normales disponibles "
                                          "sont 1971-2000, 1981-2010 et 1991-2020.")


@pytest.mark.parametrize(("year", "first", "last", "origin"), [
    (1985, 1978, 1992, "observed"), (1972, 1970, 1984, "observed"), (2020, 2011, 2025, "observed"),
    (2030, 2027, 2041, "simulated"), (2084, 2077, 2091, "simulated"), (2098, 2086, 2100, "simulated"),
])
def test_the_climate_window_is_15_years_inside_one_source(year, first, last, origin) -> None:
    from src.app.api import climate
    period, start, end = climate.window(year)
    assert (start, end) == (first, last)
    assert ("simulated" if period.source == "cordex" else "observed") == origin


def test_the_climate_diagram_is_twelve_monthly_means(client: TestClient) -> None:
    response = client.get("/api/climate", params={**GRENOBLE, "start": "2084-06-21", "end": "2084-09-20"})
    assert response.status_code == 200
    answer = response.json()
    assert answer["window"] == {"start_year": 2077, "end_year": 2091, "origin": "simulated",
                                "source": "CORDEX EUR-11 corrigé"}
    assert answer["reference"]["start_year"] == 1991 and answer["reference"]["origin"] == "observed"
    assert [m["month"] for m in answer["months"]] == list(range(1, 13))

    # July, by brute force on the small store: tas from the 0.1 deg cell, pr at 0.25 deg,
    # rain as mean daily rain x 31 days.
    july = [date(y, 7, d) for y in range(2077, 2092) for d in range(1, 32)]
    temperature = sum(expected("cordex", d, "tas", fine=True) for d in july) / len(july)
    rain = sum(expected("cordex", d, "pr") for d in july if d != GAP) / len([d for d in july if d != GAP]) * 31
    served = answer["months"][6]
    assert served["temperature_mean"] == pytest.approx(temperature, abs=0.051)
    assert served["precipitation"] == pytest.approx(rain, abs=0.051)
    assert served["dry"] is (rain <= 2 * temperature)


def test_the_climate_diagram_follows_the_reference(client: TestClient) -> None:
    answer = client.get("/api/climate", params={**GRENOBLE, "start": "1985-01-01", "end": "1985-01-31",
                                                "reference": 1971}).json()
    assert answer["window"]["start_year"] == 1978 and answer["window"]["source"] == "ERA5"
    assert (answer["reference"]["start_year"], answer["reference"]["end_year"]) == (1971, 2000)
    refused = client.get("/api/climate", params={**GRENOBLE, "start": "2026-06-21", "end": "2026-06-23"})
    assert refused.status_code != 200
