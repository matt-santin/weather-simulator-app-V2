"""The places a name may mean: the search of the home form, on the site's own server.

The places are data/serve/geocode.sqlite (src.store.geocode: GeoNames, CC BY
4.0, the source Open-Meteo's geocoder used, which the browser called until
27/11/2026). Read-only, one connection per thread. Optional: without the file
the route says so and the form cannot find a place.

A name is searched by its start, without accents or case ("pontar" finds
Pontarlier, "st jean" Saint-Jean-de-Luz); a name matched whole comes first,
then the most populated.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

from src.config import DATA
from src.app.domain.names import key

PATH = Path(os.environ.get("WSA_GEOCODE", DATA / "serve" / "geocode.sqlite"))
MAX_COUNT = 20

QUERY = """
SELECT p.id, p.name, p.admin1, p.country, p.latitude, p.longitude, p.population, p.elevation
FROM names AS n JOIN places AS p ON p.id = n.id
WHERE n.key >= ? AND n.key < ?
GROUP BY p.id
ORDER BY MAX(n.key = ?) DESC, p.population DESC, p.name
LIMIT ?
"""


class Geocoder:
    def __init__(self, path: Path = PATH) -> None:
        self.path = path
        stat = path.stat()
        self.stamp = f"{stat.st_size}-{stat.st_mtime_ns}"
        self._local = threading.local()

    def _db(self) -> sqlite3.Connection:
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
            self._local.db = db
        return db

    def search(self, name: str, count: int = 10) -> list[dict]:
        """The places whose name starts with `name`, at most `count`."""
        k = key(name)
        if not k:
            return []
        rows = self._db().execute(QUERY, (k, k + "￿", k, min(count, MAX_COUNT))).fetchall()
        return [
            {"id": r[0], "name": r[1], "admin1": r[2], "country_code": r[3], "latitude": r[4],
             "longitude": r[5], "population": r[6], "elevation": r[7]}
            for r in rows
        ]


def open_geocoder(path: Path = PATH) -> Geocoder | None:
    return Geocoder(path) if path.exists() else None
