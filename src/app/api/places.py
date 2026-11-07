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


class Places:
    def __init__(self, path: Path = PATH) -> None:
        with open(path, encoding="utf-8") as lines:
            rows = list(csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE))
        self.names = [row["name"] for row in rows]
        self.countries = [row["country"] for row in rows]
        self.lat = np.radians([float(row["latitude"]) for row in rows])
        self.lon = np.radians([float(row["longitude"]) for row in rows])
        self.degrees = [(float(row["latitude"]), float(row["longitude"])) for row in rows]

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
