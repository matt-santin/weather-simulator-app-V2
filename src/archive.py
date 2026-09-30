"""Move finished data files from the Mac to the external drive.

    python -m src.archive           copy and verify, keep the local copies
    python -m src.archive --free    same, then delete the verified local copies

Run from the repo root, with the drive plugged in. Downloads keep landing in
./data on the Mac, so the drive need not stay plugged in.

Every .nc file under DATA, and every file inside a .zarr folder (the serving
store, src.store.build), is copied to the same path under ARCHIVE, read back
from the drive and compared with the local one by MD5, then listed in MANIFEST.
Only a file listed there is ever deleted from the Mac. The downloaders read
MANIFEST, so they skip what is on the drive.

A file younger than SETTLE seconds is left alone: CORDEX extracts straight to
the final name, so a young file may still be written. Folders whose name starts
with "_" (tests) stay on the Mac. Logs and provenance notes are copied at every
run and never deleted.

A .zarr store can be rebuilt: its files are copied again when their MD5 no
longer matches the one in MANIFEST.
"""

import fcntl
import hashlib
import os
import shutil
import sys
import time
from pathlib import Path

from src.config import ARCHIVE, DATA, MANIFEST, archived

SETTLE = 300
F_NOCACHE = 48  # macOS fcntl: read from the disk, not from the memory cache


def digest(path: Path, nocache: bool = False) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        if nocache:
            fcntl.fcntl(f, F_NOCACHE, 1)
        while chunk := f.read(8 << 20):
            h.update(chunk)
    return h.hexdigest()


def local(pattern: str) -> list[tuple[Path, Path]]:
    out = []
    for p in sorted(DATA.rglob(pattern)):
        rel = p.relative_to(DATA)
        if any(part.startswith(("_", ".")) for part in rel.parts) or p == MANIFEST:
            continue
        out.append((p, rel))
    return out


def stores() -> list[tuple[Path, Path]]:
    """Files inside .zarr folders under DATA."""
    return [(p, rel) for p, rel in local("*")
            if p.is_file() and any(part.endswith(".zarr") for part in rel.parts)]


def digests() -> dict[str, str]:
    """Archived files, as path relative to DATA: MD5, the last one listed."""
    if not MANIFEST.exists():
        return {}
    return {rel: md5 for rel, _, md5 in (l.split("\t") for l in MANIFEST.read_text().splitlines())}


def copy(src: Path, dst: Path) -> None:
    # copyfile moves the data only: no extended attributes, so no "._" files
    # on the exFAT drive. The .part name keeps a cut copy from passing as whole.
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def main(argv: list[str]) -> int:
    free = "--free" in argv
    if not ARCHIVE.parents[1].exists():
        print(f"Disque absent : {ARCHIVE.parents[1]} introuvable.")
        return 1

    done, md5s = archived(), digests()
    files = [(p, rel) for p, rel in local("*.nc") + stores()
             if time.time() - p.stat().st_mtime >= SETTLE]
    todo = [(p, rel) for p, rel in files
            if str(rel) not in done or (".zarr" in str(rel) and digest(p) != md5s[str(rel)])]
    print(f"{len(files)} fichiers .nc et .zarr sur le Mac, {len(todo)} a archiver, "
          f"{sum(p.stat().st_size for p, _ in todo) / 1e9:.1f} Go", flush=True)

    t0, moved, failed = time.time(), 0, []
    with MANIFEST.open("a") as manifest:
        for i, (p, rel) in enumerate(todo, 1):
            dst = ARCHIVE / rel
            size, md5 = p.stat().st_size, digest(p)
            copy(p, dst)
            if dst.stat().st_size != size or digest(dst, nocache=True) != md5:
                failed.append(str(rel))
                print(f"  ECHEC verification : {rel}", flush=True)
                continue
            manifest.write(f"{rel}\t{size}\t{md5}\n")
            manifest.flush()
            os.fsync(manifest.fileno())
            moved += size
            if i % 50 == 0 or i == len(todo):
                rate = moved / 1e6 / (time.time() - t0)
                print(f"  [{i}/{len(todo)}] {moved / 1e9:6.1f} Go  {rate:4.0f} Mo/s", flush=True)

    for p, rel in local("*.log") + local("*.md") + local("*.json"):
        copy(p, ARCHIVE / rel)
    copy(MANIFEST, ARCHIVE / MANIFEST.name)

    if free:
        done = archived()
        freed = 0
        for p, rel in files:
            dst = ARCHIVE / rel
            if str(rel) in done and dst.exists() and dst.stat().st_size == done[str(rel)] == p.stat().st_size:
                freed += p.stat().st_size
                p.unlink()
        print(f"{freed / 1e9:.1f} Go liberes sur le Mac")

    if failed:
        print(f"{len(failed)} echecs, gardes sur le Mac : {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
