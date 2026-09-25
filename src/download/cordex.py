"""Pull CORDEX years for the retained pair, one variable per request.

    python -m src.download.cordex 1970-1990
    python -m src.download.cordex 1970 1971 2044

Run from the repo root. The pair is fixed in CLAUDE.md: EC-Earth2 driving SMHI-RCA4 on EUR-11 at 12 km,
member r12i1p1, the only member rcp_4_5 offers, so the only one that joins the
historical run without a break in 2006. The experiment follows the year:
historical up to 2005, rcp_4_5 from 2006.

**The CDS returns only the first variable of a list, silently.** Verified on
2026-09-20: asking for three gave one, the first. So every variable gets its own
request, and the name of what comes back is checked against what was asked.

Files land flat in config.CORDEX under their CORDEX names, which already
carry variable, domain, driving model, experiment, member, regional model and
period. The zip and its provenance picture are dropped, and provenance.json only
once: every copy says the same thing bar a request id, and what it does add (the
ESGF source version) is recorded in PROVENANCE.md.
Anything already on disk is skipped, so the run is resumable.
"""

import sys
import zipfile
from pathlib import Path

from src.config import CORDEX, held

DATASET = "projections-cordex-domains-single-levels"
OUT = CORDEX

GCM, RCM, MEMBER = "ichec_ec_earth", "smhi_rca4", "r12i1p1"
FIRST, SWITCH, LAST = 1970, 2006, 2100

VARIABLES = {
    "tas": "2m_air_temperature",
    "tasmax": "maximum_2m_temperature_in_the_last_24_hours",
    "tasmin": "minimum_2m_temperature_in_the_last_24_hours",
    "hurs": "2m_relative_humidity",
    "huss": "2m_surface_specific_humidity",
    "pr": "mean_precipitation_flux",
    "clt": "total_cloud_cover",
    "sfcWind": "10m_wind_speed",
    "rsds": "surface_solar_radiation_downwards",
    "rlds": "surface_thermal_radiation_downward",
    "rsus": "surface_upwelling_shortwave_radiation",
    "ps": "surface_pressure",
    "evspsbl": "evaporation",
    # Nothing here is displayed. zg500 is the reference field for weather
    # regimes and blocking, and the one that says whether the driving model
    # places the jet correctly: the check that would settle which model to
    # trust. Sea-level pressure was dropped in its favour: it answers the same
    # questions less well, being extrapolated beneath the mountains.
    "zg500": "500hpa_geopotential_height",
}

# Also dropped: 850hpa_u_component_of_the_wind and its northward twin.


def experiment(year: int) -> str:
    return "historical" if year < SWITCH else "rcp_4_5"


def already(year: int, short: str) -> int | None:
    # The experiment is deliberately left out of the pattern. The CDS wants
    # "rcp_4_5" in a request, but names the file it returns "rcp45", and
    # spelling it here once more made every year from 2006 on look missing:
    # the run re-downloaded what it already held. The year settles the
    # experiment anyway, so the pattern need not repeat it.
    # Files moved to the external drive count as held.
    return held(OUT / f"{short}_EUR-11_*_day_{year}0101-{year}1231.nc")


def years_from(argv: list[str]) -> list[int]:
    out: list[int] = []
    for a in argv:
        if "-" in a:
            lo, hi = a.split("-")
            out += list(range(int(lo), int(hi) + 1))
        else:
            out.append(int(a))
    return [y for y in sorted(set(out)) if FIRST <= y <= LAST]


def unpack(zpath: Path, short: str) -> Path:
    with zipfile.ZipFile(zpath) as z:
        nc = [n for n in z.namelist() if n.endswith(".nc")]
        if len(nc) != 1 or not Path(nc[0]).name.startswith(short + "_"):
            raise SystemExit(f"{zpath.name}: recu {nc}, attendu {short}_...: collecte arretee")
        z.extract(nc[0], OUT)
        target = OUT / nc[0]
        # Provenance is the same for every request but the request id: the
        # source version, rook and clisops. One sample is kept, in PROVENANCE.md.
        sample = OUT / "provenance-sample.json"
        if not sample.exists():
            prov = [n for n in z.namelist() if n.endswith("provenance.json")]
            if prov:
                with z.open(prov[0]) as src:
                    sample.write_bytes(src.read())
    zpath.unlink()
    return target


def fetch(client, year: int, short: str, long: str) -> int:
    hit = already(year, short)
    if hit:
        return hit

    request = {
        "domain": "europe",
        "experiment": experiment(year),
        "horizontal_resolution": "0_11_degree_x_0_11_degree",
        "temporal_resolution": "daily_mean",
        "variable": [long],
        "gcm_model": GCM,
        "rcm_model": RCM,
        "ensemble_member": MEMBER,
        "year": [str(year)],
        "month": [f"{m:02d}" for m in range(1, 13)],
    }
    tmp = OUT / f".{short}_{year}.part"
    client.retrieve(DATASET, request, str(tmp))
    return unpack(tmp, short).stat().st_size


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    if not (Path.home() / ".cdsapirc").exists():
        print("Missing ~/.cdsapirc: create it from your CDS account page.")
        return 1

    import cdsapi

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob(".*.part"):
        stale.unlink()

    ys = years_from(argv)
    todo = [(y, s, l) for y in ys for s, l in VARIABLES.items()]
    print(f"{len(ys)} annees ({ys[0]}-{ys[-1]}) x {len(VARIABLES)} variables = {len(todo)} requetes")

    client = cdsapi.Client(quiet=True, progress=False)
    total = 0
    failed: list[tuple[int, str]] = []
    for n, (y, s, l) in enumerate(todo, 1):
        # The CDS fails a request now and then with a server-side
        # RoocsRuntimeError. Observed transient: the same request succeeded on
        # the next try. One failure must not end the run, so it is retried
        # twice, then noted and stepped over.
        for attempt in (1, 2, 3):
            try:
                size = fetch(client, y, s, l)
                break
            except SystemExit:
                raise
            except Exception as err:
                if attempt == 3:
                    failed.append((y, s))
                    print(f"  [{n}/{len(todo)}] {y} {s:8} ECHEC apres 3 essais : "
                          f"{type(err).__name__}", flush=True)
                    size = 0
                else:
                    print(f"  [{n}/{len(todo)}] {y} {s:8} essai {attempt} echoue, "
                          f"on recommence", flush=True)
        total += size
        if size:
            print(f"  [{n}/{len(todo)}] {y} {s:8} {size / 1e6:6.0f} Mo"
                  f"   cumul {total / 1e9:6.2f} Go", flush=True)
    print(f"\n{len(todo) - len(failed)} fichiers, {total / 1e9:.2f} Go")
    if failed:
        print(f"{len(failed)} echecs, a relancer :")
        for y, s in failed:
            print(f"  {y} {s}")
        print("  relancer le meme appel : les fichiers presents seront sautes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
