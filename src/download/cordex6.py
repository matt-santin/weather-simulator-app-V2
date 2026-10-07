"""Pull the CORDEX-CMIP6 run from ESGF, over plain HTTP.

    python -m src.download.cordex6 tas tasmax tasmin --years 2006-2025
    python -m src.download.cordex6 sftlf orog
    python -m src.download.cordex6 tas --years 2006-2025 --dry

Run from the repo root. No account needed. The run is MPI-ESM1-2-HR r1i1p1f1
driving ICON-CLM-202407-1-1 (CLMcom-DWD) on EUR-12, rotated pole at 0.11 deg
(choice: docs/choix_modele_cmip6.md):
historical up to 2014, SSP3-7.0 from 2015. The CDS does not offer CORDEX-CMIP6
(checked 2026-10-04), so files come from the ESGF node of DKRZ, found through
the ESGF STAC catalogue.

Files are kept as ESGF cuts them, so that each one can be checked against the
SHA256 the catalogue gives: daily fields come by five years (2006-2010,
2011-2014 to close historical), 2015 alone, then 2016-2020 and so on. A file is taken
when it overlaps --years. Fixed fields (sftlf, orog, ...) are taken from the
historical experiment.

Files land flat in config.CORDEX6 under their CORDEX names. Anything already on
disk or on the drive is skipped, and a file cut off midway resumes from its
.part, so the run is resumable. The run stops when less than MIN_FREE bytes
are left on the Mac: archive with `python -m src.archive --free`, then run the
same call again. --dry lists what would be pulled and stops.
"""

import hashlib
import json
import shutil
import sys
import time
import urllib.request

from src.config import CORDEX6, held

STAC = "https://api.stac.esgf.ceda.ac.uk/search"
OUT = CORDEX6
RUN = {
    "domain_id": "EUR-12",
    "institution_id": "CLMcom-DWD",
    "driving_source_id": "MPI-ESM1-2-HR",
    "driving_variant_label": "r1i1p1f1",
    "source_id": "ICON-CLM-202407-1-1",
    "version_realization": "v1-r1",
}
SWITCH = 2015
SCENARIO = "ssp370"
FIXED = {"sftlf", "orog", "areacella", "sftgif", "sftlaf", "sfturf", "mrsofc", "rootd"}
TRIES = 10
MIN_FREE = 20e9
# The catalogue gives SHA256 as a multihash: 0x12 (sha2-256), 0x20 (32 bytes),
# then the digest.
MULTIHASH_SHA256 = "1220"


def query(experiment: str, frequency: str, variable: str) -> list[dict]:
    """STAC items of the run for one experiment, frequency and variable."""
    def eq(name, value):
        return {"op": "=", "args": [{"property": "properties.cordex-cmip6:" + name}, value]}

    args = [eq(k, v) for k, v in RUN.items()]
    args += [eq("driving_experiment_id", experiment), eq("frequency", frequency),
             eq("variable_id", variable)]
    body = {"collections": ["CORDEX-CMIP6"], "limit": 100, "filter-lang": "cql2-json",
            "filter": {"op": "and", "args": args}}
    url, items = STAC, []
    while True:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            page = json.load(r)
        items += page["features"]
        nxt = [l for l in page.get("links", []) if l.get("rel") == "next"]
        if not nxt:
            break
        url, body = nxt[0]["href"], nxt[0].get("body", body)
    # Only the latest version counts; an item withdrawn by its producer is left out.
    return [i for i in items
            if i["properties"].get("latest") and not i["properties"].get("retracted")]


def files_of(item: dict) -> list[dict]:
    out = []
    for name, a in item["assets"].items():
        if not name.endswith(".nc") or a.get("description") != "HTTPServer Link":
            continue
        checksum = a["file:checksum"]
        if not checksum.startswith(MULTIHASH_SHA256):
            raise SystemExit(f"{name}: somme de controle {checksum[:4]}, attendu SHA256 (1220)")
        out.append({"name": name, "url": a["href"], "size": a["file:size"],
                    "sha256": checksum[len(MULTIHASH_SHA256):].lower()})
    return out


def span(name: str) -> tuple[int, int]:
    start, end = name.removesuffix(".nc").rsplit("_", 1)[1].split("-")
    return int(start[:4]), int(end[:4])


def search(variable: str, first: int, last: int) -> list[dict]:
    if variable in FIXED:
        items = query("historical", "fx", variable)
        files = [f for i in items for f in files_of(i)]
        if len(files) != 1:
            raise SystemExit(f"{variable}: {len(files)} fichiers fx, attendu 1")
        return files
    out = []
    for experiment, lo, hi in (("historical", first, min(last, SWITCH - 1)),
                               (SCENARIO, max(first, SWITCH), last)):
        if lo > hi:
            continue
        items = query(experiment, "day", variable)
        if len(items) != 1:
            raise SystemExit(f"{variable} {experiment}: {len(items)} jeux de donnees, attendu 1")
        for f in files_of(items[0]):
            y0, y1 = span(f["name"])
            if y1 >= lo and y0 <= hi:
                out.append(f)
    return sorted(out, key=lambda f: f["name"])


def fetch(f: dict) -> None:
    """Pull one file into its .part, resuming where a dropped transfer stopped.

    The DKRZ node often resets connections (23 times over 12 files on
    2026-10-04). What a .part already holds is kept and only the rest is asked
    for (HTTP Range); the SHA256 is checked on the whole file at the end.
    """
    target = OUT / f["name"]
    part = target.with_name("." + target.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    h = hashlib.sha256()
    if have:
        with open(part, "rb") as old:
            while chunk := old.read(8 << 20):
                h.update(chunk)
    req = urllib.request.Request(f["url"])
    if 0 < have < f["size"]:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=120) as r:
        if have and r.status != 206:
            # The node ignored the range and sends the whole file: start over.
            have, h = 0, hashlib.sha256()
        with open(part, "ab" if have else "wb") as out:
            while chunk := r.read(8 << 20):
                h.update(chunk)
                out.write(chunk)
    size = part.stat().st_size
    if size != f["size"] or h.hexdigest() != f["sha256"]:
        part.unlink()
        raise ValueError(f"taille ou SHA256 differents ({size} octets)")
    part.rename(target)


def parse(argv: list[str]) -> tuple[list[str], int, int, bool]:
    variables, first, last, dry = [], 1970, 2100, False
    it = iter(argv)
    for a in it:
        if a == "--years":
            span_ = next(it)
            lo, _, hi = span_.partition("-")
            first, last = int(lo), int(hi or lo)
        elif a == "--dry":
            dry = True
        else:
            variables.append(a)
    return variables, first, last, dry


def main(argv: list[str]) -> int:
    variables, first, last, dry = parse(argv)
    if not variables:
        print(__doc__)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    files = [f for v in variables for f in search(v, first, last)]
    todo = [f for f in files if not held(OUT / f["name"])]
    print(f"{len(files)} fichiers ESGF ({', '.join(variables)}, {first}-{last}), "
          f"{len(todo)} a telecharger, {sum(f['size'] for f in todo) / 1e9:.2f} Go", flush=True)
    if dry:
        for f in todo:
            print(f"  {f['name']}  {f['size'] / 1e6:5.0f} Mo")
        return 0

    failed = []
    for n, f in enumerate(todo, 1):
        if shutil.disk_usage(OUT).free - f["size"] < MIN_FREE:
            print(f"Moins de {MIN_FREE / 1e9:.0f} Go libres apres {f['name']} : arret. "
                  "Archiver (python -m src.archive --free), puis relancer le meme appel.", flush=True)
            break
        t0 = time.time()
        # A transfer can drop: it resumes from its .part, up to TRIES times,
        # then the file is noted and stepped over (its .part is kept for the
        # next run). A corrupt file is deleted and pulled again.
        for attempt in range(1, TRIES + 1):
            try:
                fetch(f)
                print(f"  [{n}/{len(todo)}] {f['name']}  {f['size'] / 1e6:5.0f} Mo  "
                      f"{time.time() - t0:4.0f} s  SHA256 ok", flush=True)
                break
            except Exception as err:
                print(f"  [{n}/{len(todo)}] {f['name']} essai {attempt} echoue : "
                      f"{type(err).__name__} {err}", flush=True)
                if attempt == TRIES:
                    failed.append(f["name"])
                else:
                    time.sleep(10)
    if failed:
        print(f"{len(failed)} echecs, relancer le meme appel : {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
