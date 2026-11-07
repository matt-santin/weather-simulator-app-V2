"""The places of the map page: which town a clicked cell is near.

    python -m src.store.places

Source: GeoNames (geonames.org, CC BY 4.0), in data/fixed/geonames/:

- cities5000.txt: every populated place of 5 000 people or more
  (download.geonames.org/export/dump/cities5000.zip);
- alternate_fr.tsv: the French names of alternateNamesV2.txt (same address,
  alternateNamesV2.zip), the lines whose language is "fr".

Kept: the places inside the frame of the map (outlines.BOX), less the parts
of a town (PPLX), the historical and the abandoned places (PPLH, PPLQ). The
name is the French one where GeoNames has one (Vienne, Bruxelles, Londres),
else its own; in France its own, which is the French one already.

Writes data/serve/places.tsv: name, latitude, longitude, country code,
population, sorted by population. Read by src.app.api.places.
"""

from __future__ import annotations

import csv

from src.config import DATA
from src.store.outlines import BOX

SOURCE = DATA / "fixed" / "geonames"
TARGET = DATA / "serve" / "places.tsv"
LEFT_OUT = {"PPLX", "PPLH", "PPLQ"}


def french_names(path=SOURCE / "alternate_fr.tsv") -> dict[str, str]:
    """geonameid: its French name, the preferred one first; colloquial and
    historic names never."""
    best: dict[str, tuple[int, str]] = {}
    with open(path, encoding="utf-8") as lines:
        for row in csv.reader(lines, delimiter="\t", quoting=csv.QUOTE_NONE):
            row += [""] * (8 - len(row))
            _, gid, _, name, preferred, short, colloquial, historic = row[:8]
            if colloquial == "1" or historic == "1":
                continue
            rank = 0 if preferred == "1" else 1 if short != "1" else 2
            if gid not in best or rank < best[gid][0]:
                best[gid] = (rank, name)
    return {gid: name for gid, (_, name) in best.items()}


def build() -> int:
    french = french_names()
    kept = []
    with open(SOURCE / "cities5000.txt", encoding="utf-8") as lines:
        for row in csv.reader(lines, delimiter="\t", quoting=csv.QUOTE_NONE):
            gid, name, lat, lon, code, country, population = (
                row[0], row[1], float(row[4]), float(row[5]), row[7], row[8], int(row[14] or 0))
            if code in LEFT_OUT:
                continue
            if not (BOX["south"] <= lat <= BOX["north"] and BOX["west"] <= lon <= BOX["east"]):
                continue
            if country != "FR":
                name = french.get(gid, name)
            kept.append((name, round(lat, 4), round(lon, 4), country, population))
    kept.sort(key=lambda place: -place[4])
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with open(TARGET, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        writer.writerow(("name", "latitude", "longitude", "country", "population"))
        writer.writerows(kept)
    return len(kept)


if __name__ == "__main__":
    print(f"{build()} lieux : {TARGET}")
