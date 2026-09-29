"""Pull the E-OBS gridded station analysis, used to check the correction.

    python -m src.download.eobs

Run from the repo root. E-OBS is served by KNMI as one file per variable
covering 1950 to the last full year, straight over HTTP: no queue, no key.
Retained: version 33.0e (May 2026, 1950-2025), regular 0.25 deg grid,
ensemble mean for the seven variables that match a CORDEX one, ensemble spread
for tx, tn and rr (where E-OBS itself is unsure: few stations, mountains), and
the grid elevation. pp is left out: it is reduced to sea level, not comparable
with ps.

Files land flat in config.EOBS under their KNMI names. A download goes to a
.part file, resumed if cut (curl -C -), checked against the size the server
announces, then renamed. Anything already on disk or on the drive is skipped.
"""

import subprocess
import sys

from src.config import EOBS, held

VERSION = "v33.0e"
BASE = "https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.25deg_reg_ensemble"

# E-OBS name: the CORDEX variable it is compared with.
MEAN = {
    "tg": "tas",
    "tx": "tasmax",
    "tn": "tasmin",
    "rr": "pr",
    "hu": "hurs",
    "fg": "sfcWind",
    "qq": "rsds",
}
SPREAD = ["tx", "tn", "rr"]

FILES = (
    [f"{v}_ens_mean_0.25deg_reg_{VERSION}.nc" for v in MEAN]
    + [f"{v}_ens_spread_0.25deg_reg_{VERSION}.nc" for v in SPREAD]
    + [f"elev_ens_0.25deg_reg_{VERSION}.nc"]
)


def remote_size(url: str) -> int:
    head = subprocess.run(["curl", "-sfI", url], capture_output=True, text=True, check=True)
    for line in head.stdout.splitlines():
        if line.lower().startswith("content-length:"):
            return int(line.split(":")[1])
    raise SystemExit(f"{url}: pas de taille annoncee")


def fetch(name: str) -> int:
    hit = held(EOBS / name)
    if hit:
        return hit
    url = f"{BASE}/{name}"
    size = remote_size(url)
    part = EOBS / f".{name}.part"
    subprocess.run(["curl", "-sfL", "--retry", "3", "-C", "-", "-o", str(part), url], check=True)
    got = part.stat().st_size
    if got != size:
        raise SystemExit(f"{name}: {got} octets recus, {size} annonces")
    part.rename(EOBS / name)
    return size


def main() -> int:
    EOBS.mkdir(parents=True, exist_ok=True)
    total = 0
    for n, name in enumerate(FILES, 1):
        size = fetch(name)
        total += size
        print(f"  [{n}/{len(FILES)}] {name:40} {size / 1e6:6.0f} Mo"
              f"   cumul {total / 1e9:5.2f} Go", flush=True)
    print(f"\n{len(FILES)} fichiers, {total / 1e9:.2f} Go")
    return 0


if __name__ == "__main__":
    sys.exit(main())
