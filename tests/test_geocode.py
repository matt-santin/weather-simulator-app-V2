"""The place search of the home form (src.app.api.geocode, src.app.domain.names)."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.app.api import app as api
from src.app.api.geocode import Geocoder
from src.app.domain.names import key
from src.app.store import Store


@pytest.fixture()
def client(store_path):
    store = Store(store_path)
    api.app.dependency_overrides[api.get_store] = lambda: store
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()

PLACES = [
    # id, name, admin1, country, lat, lon, population, elevation, searchable spellings
    (1, "Pontarlier", "Bourgogne-Franche-Comté", "FR", 46.90, 6.36, 17000, 834, ["Pontarlier"]),
    (2, "Pontarmé", "Hauts-de-France", "FR", 49.15, 2.56, 900, 59, ["Pontarmé"]),
    (3, "Saint-Jean-de-Luz", "Nouvelle-Aquitaine", "FR", 43.39, -1.66, 14000, 8, ["Saint-Jean-de-Luz"]),
    (4, "Munich", "Bavière", "DE", 48.14, 11.58, 1260000, 524, ["Munich", "München"]),
    (5, "München", "Brandebourg", "DE", 52.0, 14.0, 0, 85, ["München"]),
    (6, "Szetlew", "voïvodie de Grande-Pologne", "PL", 52.13, 18.0, 0, 85, ["Szetlew"]),
]


@pytest.fixture()
def geocoder(tmp_path) -> Geocoder:
    path = tmp_path / "geocode.sqlite"
    db = sqlite3.connect(path)
    db.executescript("""CREATE TABLE places (id INTEGER PRIMARY KEY, name TEXT, country TEXT, admin1 TEXT,
                        latitude REAL, longitude REAL, population INTEGER, elevation INTEGER);
                        CREATE TABLE names (key TEXT, id INTEGER);""")
    for gid, name, admin1, country, lat, lon, pop, elev, spellings in PLACES:
        db.execute("INSERT INTO places VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (gid, name, country, admin1, lat, lon, pop, elev))
        for spelled in {key(s) for s in spellings}:
            db.execute("INSERT INTO names VALUES (?, ?)", (spelled, gid))
    db.commit()
    db.close()
    return Geocoder(path)


def test_a_name_is_searched_without_accents_case_or_abbreviations() -> None:
    assert key("Saint-Jean-de-Luz") == "saint jean de luz"
    assert key("st jean de luz") == key("Saint-Jean-de-Luz")
    assert key("MÜNCHEN") == "munchen"
    assert key("Kraków") == key("Krakow") == "krakow"
    assert key("L'Haÿ-les-Roses") == "l hay les roses"


def test_the_start_of_a_name_finds_the_largest_first(geocoder: Geocoder) -> None:
    assert [p["name"] for p in geocoder.search("pontar")] == ["Pontarlier", "Pontarmé"]
    assert [p["name"] for p in geocoder.search("St Jean de Luz")] == ["Saint-Jean-de-Luz"]
    assert geocoder.search("Szetlew")[0]["elevation"] == 85
    assert geocoder.search("   ") == []


def test_a_name_matched_whole_comes_first_then_the_population(geocoder: Geocoder) -> None:
    """Both are called München; the city, by far the larger, leads."""
    found = geocoder.search("München")
    assert [p["id"] for p in found] == [4, 5]
    assert found[0]["admin1"] == "Bavière" and found[0]["country_code"] == "DE"


def test_the_route_says_which_places_the_site_covers(client: TestClient, geocoder: Geocoder) -> None:
    api.app.dependency_overrides[api.get_geocoder] = lambda: geocoder
    try:
        answer = client.get("/api/geocode", params={"name": "pontar"}).json()
        assert [p["name"] for p in answer["results"]] == ["Pontarlier", "Pontarmé"]
        assert all(isinstance(p["covered"], bool) for p in answer["results"])
        assert client.get("/api/geocode", params={"name": ""}).status_code >= 400
    finally:
        api.app.dependency_overrides.pop(api.get_geocoder, None)


def test_no_database_no_search(client: TestClient) -> None:
    api.app.dependency_overrides[api.get_geocoder] = lambda: None
    try:
        assert client.get("/api/geocode", params={"name": "Paris"}).status_code == 503
    finally:
        api.app.dependency_overrides.pop(api.get_geocoder, None)
