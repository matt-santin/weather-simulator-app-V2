"""Mountain stations against E-OBS and ERA5-Land, daily Tx and Tn, 1991-2014.

    python -m src.validation.stations_montagne          (LaCie plugged in)

Who is right on the Alpine crests in winter, where E-OBS is 3 to 6 K warmer
than ERA5-Land and ERA5 on Tn (src.validation.eobs_era5land densite)? ECA&D blended
series (data/stations/ecad/blend/ECA_blend_tx.zip, _tn.zip, non-commercial
licence: validation only) of every station at or above MIN_ELEV m, valid days
only (quality code 0). At each station:
  - ERA5-Land: the nearest land cell (0.1 deg);
  - E-OBS: the native cell holding the station, and the mean of the 4 cells
    around the ERA5-Land cell (the remap of eobs_land, what a correction
    against E-OBS would use);
  - altitude of the cells: E-OBS elevation (GTOPO30 mean), also used for the
    ERA5-Land cell (its own orography is not on disk).
Gaps source - station over the days both have: mean Tn of DJF, mean Tx of JJA,
mean annual extremes (TNn, TXx), raw and brought to the station altitude with
LAPSE (a mean lapse rate: wrong under inversions, hence the raw values and the
subset of stations within DZ m of their cell). E-OBS input stations (ids of
stations_info_*_v33.0e.txt, the ECA&D ids) are flagged: E-OBS follows them by
construction, ERA5-Land does not.
Outputs: data/correction/mpi/eobs_land/sommets.log, sommets.csv.
"""

import io
import warnings
import zipfile

import numpy as np
import pandas as pd
import xarray as xr

from src.config import ARCHIVE, ROOT
from src.validation.eobs_era5land import OUT, stations
from src.correction.qdm010 import land_file

BLEND = ROOT / "data" / "stations" / "ecad" / "blend"
EOBS = ARCHIVE / "eobs" / "0.1deg"
P = (1991, 2014)
MIN_ELEV = 800
MIN_VALID = 0.7
LAPSE = 0.0065  # K/m
DZ = 200
ALPS = (43.5, 48.5, 5.0, 17.0)
FIELDS = {"tx": ("TX", "t2mmax", (6, 7, 8), np.max), "tn": ("TN", "t2mmin", (12, 1, 2), np.min)}


def dms(s):
    sign = -1 if s.strip().startswith("-") else 1
    d, m, sec = (float(x) for x in s.strip().lstrip("+-").split(":"))
    return sign * (d + m / 60 + sec / 3600)


def station_list(z):
    text = z.read("stations.txt").decode("latin1").splitlines()
    start = next(i for i, l in enumerate(text) if l.startswith("STAID"))
    rows = []
    for line in text[start + 1:]:
        p = line.split(",")
        if len(p) < 6 or not p[0].strip():
            continue
        rows.append((int(p[0]), p[1].strip(), p[2].strip(), dms(p[3]), dms(p[4]), float(p[5])))
    return pd.DataFrame(rows, columns=["id", "name", "cn", "lat", "lon", "elev"]).set_index("id")


def series(z, key, sid):
    name = f"{key}_STAID{sid:06d}.txt"
    try:
        raw = z.read(name).decode("latin1")
    except KeyError:
        return None
    lines = raw.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("STAID"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    df = df[(df[f"Q_{key}"] == 0)]
    s = pd.Series(df[key].values / 10, index=pd.to_datetime(df.DATE.astype(str)))
    return s.loc[f"{P[0]}":f"{P[1]}"]


def main():
    zips = {e: zipfile.ZipFile(BLEND / f"ECA_blend_{e}.zip") for e in FIELDS}
    st = station_list(zips["tx"])
    land0 = xr.open_dataset(land_file("t2mmax", 1991)).t2mmax.isel(time=0)
    elat, elon = (xr.open_dataset(EOBS / "tx_ens_mean_0.1deg_reg_v33.0e.nc")[c].values for c in ("latitude", "longitude"))
    st = st[(st.elev >= MIN_ELEV) & (st.lat > elat[0]) & (st.lat < elat[-1]) & (st.lon > elon[0]) & (st.lon < elon[-1])]
    days = pd.date_range(f"{P[0]}-01-01", f"{P[1]}-12-31")
    obs = {}
    for e, (key, *_rest) in FIELDS.items():
        cols = {}
        for sid in st.index:
            s = series(zips[e], key, sid)
            if s is not None and s.size >= MIN_VALID * days.size:
                cols[sid] = s
        obs[e] = pd.DataFrame(cols).reindex(days)
    keep = sorted(set(obs["tx"].columns) | set(obs["tn"].columns))
    st = st.loc[keep]
    print(f"{len(st)} stations >= {MIN_ELEV} m avec >= {MIN_VALID:.0%} de jours valides sur {P[0]}-{P[1]}", flush=True)

    # Cells: nearest ERA5-Land land cell; E-OBS native cell; the 4 E-OBS cells around the ERA5-Land cell.
    llat, llon = land0.latitude.values, land0.longitude.values
    valid = np.isfinite(land0.values)
    vi, vj = np.nonzero(valid)
    li, lj = [], []
    for la, lo in zip(st.lat, st.lon):
        d = (llat[vi] - la) ** 2 + ((llon[vj] - lo) * np.cos(np.deg2rad(la))) ** 2
        k = np.argmin(d)
        li.append(vi[k])
        lj.append(vj[k])
    li, lj = np.array(li), np.array(lj)
    ni = np.abs(elat[None, :] - st.lat.values[:, None]).argmin(1)
    nj = np.abs(elon[None, :] - st.lon.values[:, None]).argmin(1)
    i0 = np.searchsorted(elat, llat[li]) - 1
    j0 = np.searchsorted(elon, llon[lj]) - 1
    pi = np.concatenate([ni, i0, i0 + 1, i0, i0 + 1])
    pj = np.concatenate([nj, j0, j0, j0 + 1, j0 + 1])
    elev = xr.open_dataset(EOBS / "elev_ens_0.1deg_reg_v33.0e.nc").elevation.values[pi, pj].reshape(5, -1)
    st["alt_eobs"] = elev[0]
    st["alt_land"] = elev[1:].mean(0)
    st["lat_land"], st["lon_land"] = llat[li], llon[lj]
    ins = {e: set(pd.read_csv(ROOT / "data" / "stations" / "ecad" / f"stations_info_{e}_v33.0e.txt", sep="|",
                              skipinitialspace=True).iloc[:, 0].astype(int)) for e in FIELDS}
    st["in_eobs"] = [sid in ins["tx"] or sid in ins["tn"] for sid in st.index]

    src = {}
    for e, (key, lfield, months, fn) in FIELDS.items():
        land = []
        for y in range(P[0], P[1] + 1):
            da = xr.open_dataset(land_file(lfield, y))[lfield]
            land.append(da.values[:, li, lj] - 273.15)
        land = np.concatenate(land)
        da = xr.open_dataset(EOBS / f"{e}_ens_mean_0.1deg_reg_v33.0e.nc")[e]
        # whole years then points in memory: scattered reads in the file are far too slow
        pts = np.concatenate([da.sel(time=str(y)).values[:, pi, pj] for y in range(P[0], P[1] + 1)])
        pts = pts.reshape(pts.shape[0], 5, -1)
        src[e] = {"ERA5-Land": land, "E-OBS maille": pts[:, 0], "E-OBS 4 voisins": pts[:, 1:].mean(1)}
        print(e, "lu", flush=True)

    rows = []
    month = days.month
    for k, sid in enumerate(st.index):
        row = {"id": sid}
        for e, (key, lfield, months, fn) in FIELDS.items():
            if sid not in obs[e]:
                continue
            o = obs[e][sid].values
            for name, x in src[e].items():
                s = x[:, k]
                both = np.isfinite(o) & np.isfinite(s)
                sea = both & np.isin(month, months)
                row[f"{e} {name}"] = (s[sea] - o[sea]).mean() if sea.sum() > 200 else np.nan
                ext = []
                for y in range(P[0], P[1] + 1):
                    m = both & (days.year == y)
                    if m.sum() >= 300:
                        ext.append(fn(s[m]) - fn(o[m]))
                row[f"{e}x {name}"] = np.mean(ext) if len(ext) >= 10 else np.nan
        rows.append(row)
    res = st.join(pd.DataFrame(rows).set_index("id"))
    res.to_csv(OUT / "sommets.csv", float_format="%.2f")

    alps = (res.lat >= ALPS[0]) & (res.lat <= ALPS[1]) & (res.lon >= ALPS[2]) & (res.lon <= ALPS[3])
    lines = [f"Stations ECA&D (series blend, jours valides) >= {MIN_ELEV} m, {P[0]}-{P[1]} : {len(res)}, "
             f"dont Alpes {alps.sum()}, dont stations d'entree E-OBS {res.in_eobs.sum()}",
             "Ecart source - station (K) : Tn moyen DJF, Tx moyen JJA, TNn et TXx (moyenne des extremes annuels)",
             f"brut | ramene a l'altitude de la station ({1000 * LAPSE:.1f} K/km, altitude de maille E-OBS)", ""]
    cols = [("tn", "Tn DJF"), ("tnx", "TNn"), ("tx", "Tx JJA"), ("txx", "TXx")]

    def table(title, mask):
        sub = res[mask]
        if len(sub) < 3:
            return
        lines.append(f"{title} ({len(sub)} stations ; altitude moyenne {sub.elev.mean():.0f} m, "
                     f"maille ERA5-Land {sub.alt_land.mean():.0f} m, maille E-OBS {sub.alt_eobs.mean():.0f} m)")
        lines.append(f"{'source':18s} " + " ".join(f"{c:>15s}" for _, c in cols))
        for name, alt in (("ERA5-Land", "alt_land"), ("E-OBS maille", "alt_eobs"), ("E-OBS 4 voisins", "alt_land")):
            adj = LAPSE * (sub[alt] - sub.elev)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                cells = [f"{np.nanmean(sub[f'{c} {name}']):+5.2f} | {np.nanmean(sub[f'{c} {name}'] + adj):+5.2f}"
                         for c, _ in cols]
            lines.append(f"{name:18s} " + " ".join(f"{c:>15s}" for c in cells))
        lines.append("")

    near = (res.alt_land - res.elev).abs() <= DZ
    for region, rm in (("Alpes", alps), ("Hors Alpes", ~alps)):
        table(f"{region}, toutes", rm)
        for lo, hi in ((800, 1200), (1200, 1800), (1800, 5000)):
            table(f"{region}, {lo}-{hi} m", rm & (res.elev >= lo) & (res.elev < hi))
        table(f"{region}, maille ERA5-Land a +- {DZ} m de la station", rm & near)
        table(f"{region}, hors reseau E-OBS", rm & ~res.in_eobs)
    lines.append("Alpes, par station (>= 1500 m) : altitude station / maille ERA5-Land ; Tn DJF ERA5-Land, E-OBS maille,"
                 " E-OBS 4 voisins (brut) ; TNn idem")
    for sid, r in res[alps & (res.elev >= 1500)].sort_values("elev", ascending=False).iterrows():
        lines.append(f"  {r['name'][:24]:24s} {r.cn} {r.elev:5.0f} / {r.alt_land:5.0f} m  "
                     f"{r['tn ERA5-Land']:+5.1f} {r['tn E-OBS maille']:+5.1f} {r['tn E-OBS 4 voisins']:+5.1f}   "
                     f"{r['tnx ERA5-Land']:+5.1f} {r['tnx E-OBS maille']:+5.1f} {r['tnx E-OBS 4 voisins']:+5.1f}"
                     f"{'' if r.in_eobs else '  (hors E-OBS)'}")
    (OUT / "sommets.log").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
