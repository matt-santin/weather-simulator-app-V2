"""Pull CORDEX files that the CDS does not offer, from the ESGF node of SMHI.

    python -m src.download.esgf sic
    python -m src.download.esgf sftlf orog

Run from the repo root. No account needed: the node serves files over plain
HTTP. Same run as src.download.cordex (EC-EARTH r12i1p1 driving RCA4 on EUR-11,
historical then rcp45) and same ESGF version, v20131026: tas 1994 from here and
from the CDS were checked equal bit for bit on 2026-09-25.

Files are kept as ESGF cuts them, five years per file for daily fields (1970
alone, then 1971-1975, ...), so that each one can be checked against the
SHA256 the search service gives. Fixed fields (fx: sftlf, orog) come with
member r0i0p0 and the historical experiment.

Files land flat in config.CORDEX, next to those of the CDS. Anything already on
disk or on the drive is skipped, so the run is resumable.
"""

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request

from src.config import CORDEX, held

NODE = "https://esg-dn1.nsc.liu.se/esg-search/search"
OUT = CORDEX
FIRST, SWITCH, LAST = 1970, 2006, 2100
FIXED = {"sftlf", "orog"}


def search(variable: str) -> list[dict]:
    """ESGF file records of the run for one variable, those that overlap FIRST-LAST."""
    fixed = variable in FIXED
    query = {
        "project": "CORDEX", "domain": "EUR-11", "driving_model": "ICHEC-EC-EARTH",
        "rcm_name": "RCA4", "rcm_version": "v1", "variable": variable,
        "ensemble": "r0i0p0" if fixed else "r12i1p1",
        "time_frequency": "fx" if fixed else "day",
        "type": "File", "latest": "true", "distrib": "false",
        "limit": 500, "format": "application/solr+json",
    }
    experiments = ["historical"] if fixed else ["historical", "rcp45"]
    out = []
    for exp in experiments:
        url = NODE + "?" + urllib.parse.urlencode({**query, "experiment": exp})
        with urllib.request.urlopen(url, timeout=120) as r:
            docs = json.load(r)["response"]["docs"]
        for d in docs:
            if not fixed:
                start, end = d["title"].rsplit("_", 1)[1].removesuffix(".nc").split("-")
                y0, y1 = int(start[:4]), int(end[:4])
                limit = (FIRST, SWITCH - 1) if exp == "historical" else (SWITCH, LAST)
                if y1 < limit[0] or y0 > limit[1]:
                    continue
            http = next(u.split("|")[0] for u in d["url"] if u.endswith("HTTPServer"))
            out.append({"name": d["title"], "size": d["size"], "url": http,
                        "sha256": d["checksum"][0].lower(),
                        "kind": d["checksum_type"][0].upper()})
    return sorted(out, key=lambda f: f["name"])


def fetch(f: dict) -> None:
    if f["kind"] != "SHA256":
        raise SystemExit(f"{f['name']}: somme de controle {f['kind']}, attendu SHA256")
    target = OUT / f["name"]
    part = target.with_name("." + target.name + ".part")
    h = hashlib.sha256()
    with urllib.request.urlopen(f["url"], timeout=120) as r, open(part, "wb") as out:
        while chunk := r.read(8 << 20):
            h.update(chunk)
            out.write(chunk)
    size = part.stat().st_size
    if size != f["size"] or h.hexdigest() != f["sha256"]:
        part.unlink()
        raise ValueError(f"taille ou SHA256 differents ({size} octets)")
    part.rename(target)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob(".*.nc.part"):
        stale.unlink()

    files = [f for v in argv for f in search(v)]
    todo = [f for f in files if not held(OUT / f["name"])]
    print(f"{len(files)} fichiers ESGF ({', '.join(argv)}), {len(todo)} a telecharger, "
          f"{sum(f['size'] for f in todo) / 1e9:.2f} Go", flush=True)

    failed = []
    for n, f in enumerate(todo, 1):
        t0 = time.time()
        # A transfer can drop or come back corrupt: two more tries, then noted
        # and stepped over.
        for attempt in (1, 2, 3):
            try:
                fetch(f)
                print(f"  [{n}/{len(todo)}] {f['name']}  {f['size'] / 1e6:5.0f} Mo  "
                      f"{time.time() - t0:4.0f} s  SHA256 ok", flush=True)
                break
            except SystemExit:
                raise
            except Exception as err:
                print(f"  [{n}/{len(todo)}] {f['name']} essai {attempt} echoue : "
                      f"{type(err).__name__} {err}", flush=True)
                if attempt == 3:
                    failed.append(f["name"])
    if failed:
        print(f"{len(failed)} echecs, relancer le meme appel : {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
