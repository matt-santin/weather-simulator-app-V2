"""The places a visitor can search for by name, in place of the Open-Meteo geocoder.

    python -m src.store.geocode

Source: GeoNames (geonames.org, CC BY 4.0), the same as Open-Meteo's geocoder
(its ids are GeoNames'), in data/fixed/geonames/:

- dl_all/allCountries.zip: every feature of every country
  (download.geonames.org/export/dump/allCountries.zip), read inside the zip;
- dl_all/admin1CodesASCII.txt: the names of the first-level regions;
- alternate_fr.tsv: the French names (src.store.places).

Kept: the populated places (feature class P) inside the frame of the map
(outlines.BOX), less the historical, abandoned and destroyed ones (PPLH, PPLQ,
PPLW) and the parts of a town (PPLX). Searched by the start of a name, without
accents or case, "st" read as "saint": the local name, its ASCII spelling and
the French name where GeoNames has one (Kraków, Krakow, Cracovie), every
alternate name above ALL_NAMES_FROM people (München for Munich). The altitude is GeoNames' `dem` (a terrain model,
SRTM or GTOPO30), the one Open-Meteo gave being from a terrain model too.

Writes data/serve/geocode.sqlite, read by src.app.api.geocode.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import sys
import time
import zipfile

from src.app.domain.names import key
from src.config import DATA
from src.store.outlines import BOX
from src.store.places import french_names

SOURCE = DATA / "fixed" / "geonames"
TARGET = DATA / "serve" / "geocode.sqlite"
# The parts of a town (Lyon 03, Paris 17) as well: the town itself is found.
LEFT_OUT = {"PPLH", "PPLQ", "PPLW", "PPLX"}
# Above this, every alternate name of GeoNames is searchable too (München for
# Munich, Firenze for Florence); below, the local, ASCII and French ones.
ALL_NAMES_FROM = 15_000
def regions(french: dict[str, str]) -> dict[str, str]:
    """"FR.84": its name, in French where GeoNames has one."""
    out = {}
    with open(SOURCE / "dl_all" / "admin1CodesASCII.txt", encoding="utf-8") as lines:
        for row in csv.reader(lines, delimiter="\t", quoting=csv.QUOTE_NONE):
            code, name, _, gid = row[:4]
            # "Région Île-de-France": the region alone, as the geocoder wrote it.
            out[code] = french.get(gid, name).removeprefix("Région ")
    return out


def build() -> None:
    t0 = time.time()
    french = french_names()
    admin = regions(french)
    TARGET.unlink(missing_ok=True)
    db = sqlite3.connect(TARGET)
    db.executescript("""
        CREATE TABLE places (id INTEGER PRIMARY KEY, name TEXT, country TEXT, admin1 TEXT,
                             latitude REAL, longitude REAL, population INTEGER, elevation INTEGER);
        CREATE TABLE names (key TEXT, id INTEGER);
    """)
    places, names = [], []
    with zipfile.ZipFile(SOURCE / "dl_all" / "allCountries.zip") as archive:
        with archive.open("allCountries.txt") as raw:
            for row in csv.reader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t",
                                  quoting=csv.QUOTE_NONE):
                if row[6] != "P" or row[7] in LEFT_OUT:
                    continue
                lat, lon = float(row[4]), float(row[5])
                if not (BOX["south"] <= lat <= BOX["north"] and BOX["west"] <= lon <= BOX["east"]):
                    continue
                gid, name, ascii_name, country = row[0], row[1], row[2], row[8]
                shown = name if country == "FR" else french.get(gid, name)
                dem = row[16] or row[15]
                places.append((int(gid), shown, country, admin.get(f"{country}.{row[10]}", ""),
                               lat, lon, int(row[14] or 0), int(dem) if dem.lstrip("-").isdigit() else None))
                spellings = {name, ascii_name, shown}
                if int(row[14] or 0) >= ALL_NAMES_FROM and row[3]:
                    spellings |= set(row[3].split(","))
                for spelled in {key(s) for s in spellings}:
                    if spelled:
                        names.append((spelled, int(gid)))
    db.executemany("INSERT INTO places VALUES (?, ?, ?, ?, ?, ?, ?, ?)", places)
    db.executemany("INSERT INTO names VALUES (?, ?)", names)
    db.execute("CREATE INDEX names_key ON names (key)")
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"{len(places)} lieux, {len(names)} noms, {TARGET} : "
          f"{TARGET.stat().st_size / 1e6:.0f} Mo, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    sys.exit(build())
