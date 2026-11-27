"""The static Köppen-Geiger maps of /climats (src.store.koppen), as written in web/static/geo."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from src.store import koppen as build
from src.store.outlines import BOX

GEO = Path(__file__).resolve().parents[1] / "web" / "static" / "geo"


def meta() -> dict:
    return json.loads((GEO / "koppen.json").read_text())


def classes(period: dict) -> np.ndarray:
    return np.array(Image.open(GEO / period["file"]))


def test_the_grid_covers_the_box_of_the_map_page() -> None:
    m = meta()
    assert m["step"] == 0.1
    assert abs(m["north"] - BOX["north"]) < 1e-6 and abs(m["west"] - BOX["west"]) < 1e-6
    assert abs(m["north"] - (m["rows"] - 1) * m["step"] - BOX["south"]) < 1e-6
    assert abs(m["west"] + (m["cols"] - 1) * m["step"] - BOX["east"]) < 1e-6


def test_two_periods_one_grey_image_each_of_the_grid_size() -> None:
    m = meta()
    assert [p["label"] for p in m["periods"]] == ["1991-2020", "2071-2100"]
    assert [p["origin"] for p in m["periods"]] == ["observed", "simulated"]
    for period in m["periods"]:
        image = Image.open(GEO / period["file"])
        assert image.mode == "L" and image.size == (m["cols"], m["rows"])
        assert classes(period).max() < len(m["codes"])


def test_the_codes_are_those_of_the_builder_and_of_the_classifier() -> None:
    """The numbers of the images are the legend of Beck et al. 2023, as the builder writes them."""
    m = meta()
    assert m["codes"] == build.CODES
    assert m["codes"][14:17] == ["Cfa", "Cfb", "Cfc"] and m["codes"][29:] == ["ET", "EF"]


def test_familiar_places_have_their_expected_family() -> None:
    """Land and sea where they should be, and the broad climates of a few towns."""
    m = meta()
    past = classes(m["periods"][0])
    at = lambda lat, lon: m["codes"][past[round((m["north"] - lat) / m["step"]), round((lon - m["west"]) / m["step"])]]
    assert at(48.86, 2.35)[0] == "C"  # Paris
    assert at(59.33, 18.07)[0] == "D"  # Stockholm
    assert at(41.89, 12.48).startswith("Cs")  # Rome
    assert at(43.0, 5.0) == ""  # the Gulf of Lion
