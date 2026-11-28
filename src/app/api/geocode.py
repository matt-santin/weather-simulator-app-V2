"""The places a name may mean: the search of the home form, on the site's own server.

The places are data/serve/geocode.sqlite (src.store.geocode: GeoNames, CC BY
4.0, the source Open-Meteo's geocoder used, which the browser called until
27/11/2026). Read-only, one connection per thread. Optional: without the file
the route says so and the form cannot find a place.

A name is searched by its start, without accents or case ("pontar" finds
Pontarlier, "st jean" Saint-Jean-de-Luz). A name matched whole comes first;
then the larger score: the decimal log of the population, plus a bonus for the
countries of the site's language (27/11/2026). France gets 2 (as if a hundred
times as many people), the other French-speaking countries 1.5: the Valence of
the Drôme comes before the one of Spain, and Rome still before a French hamlet
of that name. Ranked here rather than in SQL, which may lack a logarithm: on
the most populated matches of the world and of those countries, merged.
"""

from __future__ import annotations

import math
import os
import sqlite3
import threading
from pathlib import Path

from src.config import DATA
from src.app.domain.names import key

PATH = Path(os.environ.get("WSA_GEOCODE", DATA / "serve" / "geocode.sqlite"))
MAX_COUNT = 20
# The language of the site is French: its countries first, all else equal.
LANGUAGE_BONUS = {"FR": 2.0, "BE": 1.5, "CH": 1.5, "LU": 1.5, "MC": 1.5}
POOL = 60  # matches read from the world and from those countries, before ranking

QUERY = """
SELECT p.id, p.name, p.admin1, p.country, p.latitude, p.longitude, p.population, p.elevation,
       MAX(n.key = ?) AS whole
FROM names AS n JOIN places AS p ON p.id = n.id
WHERE n.key >= ? AND n.key < ? {where}
GROUP BY p.id
ORDER BY whole DESC, p.population DESC, p.name
LIMIT ?
"""


def score(row, typed: str) -> tuple:
    """Whole name first, then log10(population + 1) plus the language bonus, then the name.

    The bonus only where the name typed is the start of the name shown: Mons
    is also called Bergen, in Dutch, and a French reader typing Bergen means
    the one in Norway.
    """
    population, country, whole = row[6] or 0, row[3], row[8]
    bonus = LANGUAGE_BONUS.get(country, 0.0) if key(row[1]).startswith(typed) else 0.0
    return (-whole, -(math.log10(population + 1) + bonus), row[1])


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
        db = self._db()
        # U+FFFF: past every name that starts with k, in the order of the index.
        bounds = (k, k, k + "\uffff")
        world = db.execute(QUERY.format(where=""), (*bounds, POOL)).fetchall()
        countries = ", ".join("?" * len(LANGUAGE_BONUS))
        local = db.execute(QUERY.format(where=f"AND p.country IN ({countries})"),
                           (*bounds, *LANGUAGE_BONUS, POOL)).fetchall()
        merged = {r[0]: r for r in (*world, *local)}
        rows = sorted(merged.values(), key=lambda row: score(row, k))[:min(count, MAX_COUNT)]
        return [
            {"id": r[0], "name": r[1], "admin1": r[2], "country_code": r[3], "latitude": r[4],
             "longitude": r[5], "population": r[6], "elevation": r[7]}
            for r in rows
        ]


def open_geocoder(path: Path = PATH) -> Geocoder | None:
    return Geocoder(path) if path.exists() else None
