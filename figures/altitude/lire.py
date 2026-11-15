"""Tx et Tn des stations ECA&D et des mailles du site autour d'elles, 1991-2020.

    PYTHONPATH=. python figures/altitude/lire.py            (environ 10 min, sans le LaCie)

Stations retenues : dans le domaine, avec une maille à 0,1° d'altitude connue, au moins 70 % de jours
valides (code qualité 0) pour Tx ou Tn ; celles à 400 m ou plus, ou dont la maille du site est à 100 m
ou plus de leur altitude, et 400 autres tirées au hasard (témoin de plaine).
Pour chaque station : la maille que le site lui donne (Store.cell) et les 8 mailles à 0,1° qui l'entourent
(données passées servies : E-OBS ou son repli), avec leur altitude (elevation010).
Écrit data/altitude/stations.npz.
"""
import io
import zipfile
from datetime import date

import numpy as np
import pandas as pd

from src.app.store import Store
from src.config import ROOT
from src.validation.stations_montagne import BLEND, station_list

P = (1991, 2020)
MIN_VALID = 0.7
KEYS = {"tx": ("TX", "tasmax"), "tn": ("TN", "tasmin")}
OUT = ROOT / "data" / "altitude" / "stations.npz"


def series(z, key, sid, days):
    try:
        raw = z.read(f"{key}_STAID{sid:06d}.txt").decode("latin1")
    except KeyError:
        return None
    lines = raw.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("STAID"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    df = df[df[f"Q_{key}"] == 0]
    s = pd.Series(df[key].values / 10, index=pd.to_datetime(df.DATE.astype(str), errors="coerce"))
    s = s[~s.index.duplicated()].reindex(days)
    return s.values.astype("float32") if s.notna().sum() >= MIN_VALID * days.size else None


def main():
    s = Store()
    zips = {e: zipfile.ZipFile(BLEND / f"ECA_blend_{e}.zip") for e in KEYS}
    st = station_list(zips["tx"])
    st = st[(st.elev > -100) & (st.elev < 5000)]
    cells, alt = {}, {}
    for sid, r in st.iterrows():
        c = s.cell(float(r.lat), float(r.lon))
        if c is None or c.fine is None or s.elevation(c) is None:
            continue
        cells[sid], alt[sid] = c.fine, s.elevation(c)
    st = st.loc[list(cells)]
    st["cell_alt"] = pd.Series(alt)
    want = (st.elev >= 400) | ((st.cell_alt - st.elev).abs() >= 100)
    rng = np.random.default_rng(0)
    rest = st.index[~want]
    pick = set(st.index[want]) | set(rng.choice(rest, min(400, rest.size), replace=False))
    st = st.loc[sorted(pick)]
    print(f"{len(st)} stations candidates", flush=True)

    days = pd.date_range(f"{P[0]}-01-01", f"{P[1]}-12-31")
    obs = {e: {} for e in KEYS}
    for n, sid in enumerate(st.index):
        for e, (key, _) in KEYS.items():
            v = series(zips[e], key, sid, days)
            if v is not None:
                obs[e][sid] = v
        if n % 500 == 0:
            print(f"  stations lues : {n}", flush=True)
    keep = sorted(set(obs["tx"]) | set(obs["tn"]))
    st = st.loc[keep]
    print(f"{len(st)} stations avec assez de jours valides", flush=True)

    a, b = date(P[0], 1, 1), date(P[1], 12, 31)
    nan = np.full(days.size, np.nan, "float32")
    grid = {e: np.full((len(st), 9, days.size), np.nan, "float32") for e in KEYS}
    galt = np.full((len(st), 9), np.nan, "float32")
    el = s.elevations[True]
    for k, sid in enumerate(st.index):
        i, j = cells[sid]
        m = 0
        for di in (0, -1, 1):          # la maille du site d'abord, puis ses voisines
            for dj in (0, -1, 1):
                ii, jj = i + di, j + dj
                if 0 <= ii < el.shape[0] and 0 <= jj < el.shape[1] and s.domain010[ii, jj] and np.isfinite(el[ii, jj]):
                    v = s._read("era5land", (ii, jj), a, b, ("tasmax", "tasmin"))
                    galt[k, m] = el[ii, jj]
                    for e, (_, name) in KEYS.items():
                        grid[e][k, m] = v[name]
                m += 1
        if k % 300 == 0:
            print(f"  mailles lues : {k}", flush=True)
    ins = set()
    for e in KEYS:
        ins |= set(pd.read_csv(ROOT / "data" / "stations" / "ecad" / f"stations_info_{e}_v33.0e.txt", sep="|",
                               skipinitialspace=True).iloc[:, 0].astype(int))
    np.savez_compressed(
        OUT, id=st.index.values, name=st.name.values.astype(str), cn=st.cn.values.astype(str), lat=st.lat.values,
        lon=st.lon.values, elev=st.elev.values, galt=galt, in_eobs=np.array([sid in ins for sid in st.index]),
        eobs=np.array([bool(s.masks[True][cells[sid]]) for sid in st.index]),
        tx=np.stack([obs["tx"].get(sid, nan) for sid in st.index]),
        tn=np.stack([obs["tn"].get(sid, nan) for sid in st.index]), gtx=grid["tx"], gtn=grid["tn"])
    print("écrit", OUT)


if __name__ == "__main__":
    main()
