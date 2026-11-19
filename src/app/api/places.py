"""The town nearest a point of the map: the name a clicked cell is given.

The list is data/serve/places.tsv (src.store.places: GeoNames, CC BY 4.0, places
of 5 000 people or more inside the map's frame), read once. Optional, as the
map store: without it /api/place says so and the map page shows the
coordinates only.

The nearest by distance on the sphere (haversine), whatever its size: at the
scale of a map cell (0.25 deg, about 28 km), a village of 5 000 people is a
better name for the place than a city 30 km away.
"""

from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from src.config import DATA

PATH = Path(os.environ.get("WSA_PLACES", DATA / "serve" / "places.tsv"))
EARTH_KM = 6371.0
# Farther than this, the point is named by its coordinates: out at sea, or far
# from any town of the list.
MAX_KM = 50.0

# The city of another climate (Places.contrast): a large European city, about
# 800 km south of the place, or north of a place already in the south. Turkey
# is left out: the list names the districts of Istanbul as towns.
CONTRAST_MINIMUM = 500_000
CONTRAST_SHIFT = 7.2  # degrees of latitude, about 800 km
CONTRAST_SOUTH = 44.0
CONTRAST_AWAY_KM = 300.0
EUROPE = frozenset(
    "AD AL AT BA BE BG BY CH CY CZ DE DK EE ES FI FR GB GR HR HU IE IS IT LI LT LU "
    "LV MC MD ME MK MT NL NO PL PT RO RS RU SE SI SK SM UA VA XK".split()
)


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """The distance on the sphere (haversine) between two points in degrees."""
    lat1, lon1, lat2, lon2 = map(np.radians, (a[0], a[1], b[0], b[1]))
    h = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return float(2 * EARTH_KM * np.arcsin(np.sqrt(min(h, 1.0))))


class Places:
    def __init__(self, path: Path = PATH) -> None:
        # What tells one list from the next: its size and the time it was written.
        stat = path.stat()
        self.stamp = f"{stat.st_size}-{stat.st_mtime_ns}"
        with open(path, encoding="utf-8") as lines:
            rows = list(csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE))
        self.names = [row["name"] for row in rows]
        self.countries = [row["country"] for row in rows]
        self.lat = np.radians([float(row["latitude"]) for row in rows])
        self.lon = np.radians([float(row["longitude"]) for row in rows])
        self.degrees = [(float(row["latitude"]), float(row["longitude"])) for row in rows]
        self.populations = [int(row["population"] or 0) for row in rows]

    def largest(self, minimum: int) -> dict:
        """The towns of `minimum` people or more, the largest first, as columns:
        the names written on the map (/api/cities)."""
        order = sorted(
            (k for k, people in enumerate(self.populations) if people >= minimum),
            key=lambda k: -self.populations[k],
        )
        return {
            "name": [self.names[k] for k in order],
            "latitude": [self.degrees[k][0] for k in order],
            "longitude": [self.degrees[k][1] for k in order],
            "population": [self.populations[k] for k in order],
        }

    def contrast(self, latitude: float, longitude: float, served) -> dict | None:
        """The large city of another climate, for "À voir aussi" on the results
        page (19/11/2026): the European city of CONTRAST_MINIMUM people or more
        nearest the point CONTRAST_SHIFT degrees (about 800 km) south of the
        place, north for a place south of CONTRAST_SOUTH, at least CONTRAST_AWAY_KM
        from it, whose data the site serves (`served(latitude, longitude)`).
        None if there is none. Choices of the project, not a norm."""
        shift = CONTRAST_SHIFT if latitude < CONTRAST_SOUTH else -CONTRAST_SHIFT
        target = (latitude + shift, longitude)
        best = None
        for k, people in enumerate(self.populations):
            if people < CONTRAST_MINIMUM or self.countries[k] not in EUROPE:
                continue
            here = self.degrees[k]
            if km_between((latitude, longitude), here) < CONTRAST_AWAY_KM:
                continue
            far = km_between(target, here)
            if (best is None or far < best[0]) and served(*here):
                best = (far, k)
        if best is None:
            return None
        k = best[1]
        return {"name": self.names[k], "latitude": self.degrees[k][0], "longitude": self.degrees[k][1]}

    def nearest(self, latitude: float, longitude: float) -> dict | None:
        """The nearest place and how far it is (km), or None past MAX_KM."""
        lat, lon = np.radians(latitude), np.radians(longitude)
        h = (np.sin((self.lat - lat) / 2) ** 2
             + np.cos(lat) * np.cos(self.lat) * np.sin((self.lon - lon) / 2) ** 2)
        km = 2 * EARTH_KM * np.arcsin(np.sqrt(np.minimum(h, 1.0)))
        k = int(np.argmin(km))
        if km[k] > MAX_KM:
            return None
        return {
            "name": self.names[k],
            "country": self.countries[k],
            "latitude": self.degrees[k][0],
            "longitude": self.degrees[k][1],
            "distance_km": round(float(km[k]), 1),
        }


@lru_cache(maxsize=1)
def open_places(path: Path = PATH) -> Places | None:
    return Places(path) if path.exists() else None
