"""ET0 calculée (ERA5, stockage de service) contre l'ETP des stations Météo-France, 1991-2020.

    python figures/sol/meteofrance.py

Stations : données quotidiennes de meteo.data.gouv.fr (data/sol/meteofrance),
ETPMON (ETP Penman-Monteith de la station) et ETPGRILLE (ETP de la grille de
Météo-France au point), GLOT (rayonnement global, J/cm2). Rayonnements ERA5 lus
sur le disque externe à la maille de la station. Les températures du stockage
sont ramenées à l'altitude de la station.
"""
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.app.domain import et0  # noqa: E402
from src.app.store import Store  # noqa: E402
from src.config import ARCHIVE, DATA  # noqa: E402

STATIONS = {75114001: "Paris-Montsouris", 34154001: "Montpellier-Aéroport", 38384001: "Grenoble-St Geoirs",
            25056001: "Besançon", 25462001: "Pontarlier"}
START, END = date(1991, 1, 1), date(2020, 12, 31)
CACHE = DATA / "sol" / "meteofrance_era5.npz"


def stations():
    cols = ["NUM_POSTE", "LAT", "LON", "ALTI", "AAAAMMJJ", "ETPMON", "ETPGRILLE", "GLOT"]
    d = pd.concat(pd.read_csv(f, sep=";", usecols=cols) for f in sorted((DATA / "sol" / "meteofrance").glob("Q_*.csv.gz")))
    d = d[d.NUM_POSTE.isin(STATIONS) & (d.AAAAMMJJ >= 19910101) & (d.AAAAMMJJ <= 20201231)]
    d["day"] = pd.to_datetime(d.AAAAMMJJ.astype(str), format="%Y%m%d")
    return d


def radiation(lat, lon):
    if CACHE.exists():
        return dict(np.load(CACHE))
    la, lo = xr.DataArray(lat, dims="p"), xr.DataArray(lon, dims="p")
    out = {}
    for name in ("ssrd", "strd"):
        parts = []
        for y in range(START.year, END.year + 1):
            with xr.open_dataset(ARCHIVE / "era5" / "daily" / f"{name}_ERA5_day_{y}0101-{y}1231.nc") as ds:
                parts.append(ds[name].sel(latitude=la, longitude=lo, method="nearest").values)
        out[name] = np.concatenate(parts) / 1e6  # MJ m-2 par jour
    np.savez_compressed(CACHE, **out)
    return out


def main():
    obs = stations()
    meta = obs.groupby("NUM_POSTE")[["LAT", "LON", "ALTI"]].first().loc[list(STATIONS)]
    rad = radiation(meta.LAT.values, meta.LON.values)
    store = Store()
    days = pd.date_range(START.isoformat(), END.isoformat())
    doy = days.dayofyear.values
    print("Moyennes 1991-2020 sur les jours où la station donne une valeur ; mm par an = moyenne journalière x 365,25")
    print(f"{'station':22s} {'jours':>6s} {'ETPMON':>7s} {'FAO':>6s} {'flux':>6s} | {'jours':>6s} {'ETPGRILLE':>9s} {'FAO':>6s} {'flux':>6s} | rayonnement global station / ERA5 (MJ/m2/j)")
    monthly = {}
    for k, (num, name) in enumerate(STATIONS.items()):
        lat, lon, alt = (float(x) for x in meta.loc[num])
        cell = store.cell(lat, lon, alt)
        v = store.values("era5", cell, START, END, ("tasmax", "tasmin", "hurs", "sfcWind"))
        rs = rad["ssrd"][:, k]
        es, ea = et0.vapour(v["tasmax"], v["tasmin"], v["hurs"])
        rso = et0.clear_sky(et0.extraterrestrial(lat, doy), alt)
        rns = (1 - et0.ALBEDO) * rs
        rnl = {"fao": et0.net_longwave(v["tasmax"], v["tasmin"], ea, rs, rso),
               "flux": et0.SIGMA * ((v["tasmax"] + 273.16) ** 4 + (v["tasmin"] + 273.16) ** 4) / 2 - rad["strd"][:, k]}
        calc = pd.DataFrame({key: et0.reference(v["tasmax"], v["tasmin"], ea, es, et0.wind_2m(v["sfcWind"]), rns - r, et0.pressure(alt))
                             for key, r in rnl.items()}, index=days)
        calc["rs"] = rs
        o = obs[obs.NUM_POSTE == num].set_index("day").reindex(days)
        line = f"{name:22s}"
        for col in ("ETPMON", "ETPGRILLE"):
            ok = o[col].notna().values & calc.fao.notna().values
            if ok.sum() < 3000:
                line += f" {ok.sum():6d} {'':>7s} {'':>6s} {'':>6s} |"
                continue
            line += f" {ok.sum():6d} {365.25 * o[col][ok].mean():{7 if col == 'ETPMON' else 9}.0f} {365.25 * calc.fao[ok].mean():6.0f} {365.25 * calc.flux[ok].mean():6.0f} |"
            if col == "ETPMON" or name == "Pontarlier":
                m = days.month[ok]
                monthly[name] = (col, [(o[col][ok][m == i].mean(), calc.fao[ok][m == i].mean(), calc.flux[ok][m == i].mean()) for i in range(1, 13)])
        ok = o.GLOT.notna().values
        line += f" {o.GLOT[ok].mean() / 100:5.2f} / {calc.rs[ok].mean():5.2f}" if ok.sum() > 3000 else "   sans mesure"
        print(line)
    print("\nPar mois, mm par jour : station / FAO / flux")
    for name, (col, rows) in monthly.items():
        print(f"{name} ({col})")
        print("   " + "  ".join(f"{a:.1f}/{b:.1f}/{c:.1f}" for a, b, c in rows))


if __name__ == "__main__":
    main()
