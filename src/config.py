"""Paths shared by every script.

The data root defaults to ./data in the repo. Set WSA_DATA to point it
elsewhere, e.g. an external drive:

    export WSA_DATA=/Volumes/meteo/data

Downloads always land in DATA, on the Mac. Finished files are then moved to
ARCHIVE, on the external drive, by `python -m src.archive`. MANIFEST, kept in
DATA, lists what the drive holds, so that a download never fetches again a file
that was archived, even with the drive unplugged.
"""

import fnmatch
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("WSA_DATA", ROOT / "data"))
ARCHIVE = Path(os.environ.get("WSA_ARCHIVE", "/Volumes/LaCie/weather-simulator-app-V2/data"))
MANIFEST = DATA / "archive.txt"

CORDEX = DATA / "cordex" / "eur11"
ERA5 = DATA / "era5"


def archived() -> dict[str, int]:
    """Archived files, as path relative to DATA: size in bytes."""
    if not MANIFEST.exists():
        return {}
    out = {}
    for line in MANIFEST.read_text().splitlines():
        rel, size, _ = line.split("\t")
        out[rel] = int(size)
    return out


def held(pattern: Path) -> int | None:
    """Size of a file matching `pattern`, on the Mac or on the drive, else None.

    `pattern` is a path under DATA and may hold shell wildcards.
    """
    hit = next(iter(sorted(pattern.parent.glob(pattern.name))), None)
    if hit:
        return hit.stat().st_size
    rel = str(pattern.relative_to(DATA))
    for name, size in archived().items():
        if fnmatch.fnmatchcase(name, rel):
            return size
    return None
