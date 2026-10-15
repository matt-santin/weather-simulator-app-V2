"""E-OBS against ERA5-Land, daily Tx and Tn at 0.1 deg: can E-OBS replace ERA5-Land as the reference?

    python -m src.validation.eobs_era5land compute     year by year, resumable (LaCie plugged in)
    python -m src.validation.eobs_era5land report      maps, series, tables (Mac only)

compute: for each year 1970-2025, E-OBS v33.0e (ensemble mean, 0.1 deg) is
brought onto the ERA5-Land grid, each ERA5-Land cell taking the mean of the 4
E-OBS cells around it, all valid that day (E-OBS centres sit half a cell off).
ERA5-Land Tx and Tn are the max and min of hourly t2m over the UTC day; E-OBS
follows the observation day of each national network. Per cell, kept in
OUT/annees/<year>.nc:
  - mean gap E-OBS - ERA5-Land per season (calendar year: DJF is Jan, Feb and
    Dec of the same year), NaN below 80 % of common days;
  - gap of the annual extreme (TXx, max of Tx; TNn, min of Tn) over the common
    days, NaN below 80 %;
  - count of days with E-OBS, over ERA5-Land land cells (completeness).

report, over CAL (1970-2014) unless stated, regional figures on the cells
E-OBS fills on at least COMPLETE of CAL days (a fixed set of cells):
  (a) maps of the mean gap per season, of its drift (1991-2014 minus
      1970-1990) and of the TXx / TNn gaps; yearly series per region;
  (b) the gap by distance to the nearest E-OBS input station active that year
      (stations_info_tx / tn_v33.0e.txt, their START-STOP span: gaps inside
      it are not known), per period, and the drift by change of distance;
  (c) E-OBS completeness per cell: the fallback mask.
Outputs in OUT: figures and eobs_land.log.
"""

import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import cKDTree

from src.config import ARCHIVE, DATA, ROOT
from src.correction.qdm010 import land_file

OUT = DATA / "correction" / "mpi" / "eobs_land"
YEARS = range(1970, 2026)
CAL = (1970, 2014)
HALVES = ((1970, 1990), (1991, 2014))
EOBS = ARCHIVE / "eobs" / "0.1deg"
FIELDS = {"tx": "t2mmax", "tn": "t2mmin"}  # E-OBS: ERA5-Land
EXTREME = {"tx": ("txx", np.max), "tn": ("tnn", np.min)}
SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}
MIN_DAYS = 0.8
COMPLETE = 0.95
STATIONS = ROOT / "data" / "stations" / "ecad"
# Rough boxes (lat S, N, lon W, E), land cells only; they overlap at the edges.
REGIONS = {
    "France": (42.3, 51.1, -4.8, 8.2),
    "Iles Britanniques, Benelux": (50.0, 59.0, -11.0, 7.0),
    "Peninsule iberique": (36.0, 43.8, -9.5, 3.3),
    "Europe centrale, Alpes": (45.5, 55.0, 8.2, 24.0),
    "Italie, Balkans": (36.5, 45.5, 8.2, 28.0),
    "Scandinavie, Finlande": (55.0, 71.5, 4.5, 31.5),
    "Est (Baltes a Ukraine, Russie)": (45.0, 60.0, 24.0, 45.5),
    "Turquie": (36.0, 42.0, 26.0, 45.0),
    "Afrique du Nord": (27.0, 37.5, -10.0, 12.0),
}
DISTANCES = [0, 10, 25, 50, 100, 200, 5000]  # km


class Grid:
    """ERA5-Land cells inside the E-OBS 0.1 deg domain, and their 4 E-OBS neighbours."""

    def __init__(self):
        g = xr.open_dataset(land_file("t2mmax", 1970))
        e = xr.open_dataset(EOBS / "tx_ens_mean_0.1deg_reg_v33.0e.nc")
        elat, elon = e.latitude.values, e.longitude.values
        lat, lon = g.latitude.values, g.longitude.values
        self.ilat = np.flatnonzero((lat > elat[0]) & (lat < elat[-1]))
        self.ilon = np.flatnonzero((lon > elon[0]) & (lon < elon[-1]))
        self.lat, self.lon = lat[self.ilat], lon[self.ilon]
        self.i0 = np.searchsorted(elat, self.lat) - 1
        self.j0 = np.searchsorted(elon, self.lon) - 1

    def mean4(self, x):
        """(days, E-OBS lat, lon) to (days, lat, lon) of ERA5-Land; NaN if a neighbour is missing."""
        a, b = self.i0[:, None], self.j0[None, :]
        return (x[:, a, b] + x[:, a + 1, b] + x[:, a, b + 1] + x[:, a + 1, b + 1]) / 4

    def land(self, field, year):
        da = xr.open_dataset(land_file(field, year))[field]
        return da.isel(latitude=self.ilat, longitude=self.ilon).values - 273.15


# --- compute -------------------------------------------------------------------


def compute_year(grid, year, eobs):
    out = {}
    for e, f in FIELDS.items():
        obs = grid.mean4(eobs[e][e].sel(time=str(year)).values)
        ref = grid.land(f, year)
        month = pd.DatetimeIndex(eobs[e].time.sel(time=str(year)).values).month
        land = np.isfinite(ref).any(0)
        both = np.isfinite(obs) & np.isfinite(ref)
        gap = np.where(both, obs - ref, np.nan)
        out[f"n_{e}"] = (("latitude", "longitude"),
                         np.where(land, np.isfinite(obs).sum(0), -1).astype(np.int16))
        seasons = []
        for months in SEASONS.values():
            sel = np.isin(month, months)
            n = both[sel].sum(0)
            with np.errstate(invalid="ignore"):
                m = np.nansum(gap[sel], 0) / n
            seasons.append(np.where(n >= MIN_DAYS * sel.sum(), m, np.nan))
        out[f"d_{e}"] = (("season", "latitude", "longitude"), np.array(seasons, np.float32))
        name, fn = EXTREME[e]
        ok = both.sum(0) >= MIN_DAYS * len(month)
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            nan = np.nanmax if fn is np.max else np.nanmin
            ext = nan(np.where(both, obs, np.nan), 0) - nan(np.where(both, ref, np.nan), 0)
        out[f"d_{name}"] = (("latitude", "longitude"), np.where(ok, ext, np.nan).astype(np.float32))
    ds = xr.Dataset(out, coords={"season": list(SEASONS), "latitude": grid.lat, "longitude": grid.lon})
    ds.attrs["days"] = len(month)
    return ds


def compute():
    (OUT / "annees").mkdir(parents=True, exist_ok=True)
    grid = Grid()
    eobs = {e: xr.open_dataset(EOBS / f"{e}_ens_mean_0.1deg_reg_v33.0e.nc") for e in FIELDS}
    for year in YEARS:
        path = OUT / "annees" / f"{year}.nc"
        if path.exists():
            continue
        ds = compute_year(grid, year, eobs)
        enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars}
        ds.to_netcdf(path.with_suffix(".tmp"), encoding=enc)
        path.with_suffix(".tmp").rename(path)
        print(year, flush=True)


# --- report --------------------------------------------------------------------


def stations(e):
    df = pd.read_csv(STATIONS / f"stations_info_{e}_v33.0e.txt", sep="|", skipinitialspace=True)
    df.columns = [c.strip().lstrip("#") for c in df.columns]
    return pd.DataFrame({"lat": df.LAT.astype(float), "lon": df.LON.astype(float),
                         "start": pd.to_datetime(df.START.str.strip()).dt.year,
                         "stop": pd.to_datetime(df.STOP.str.strip()).dt.year})


def xyz(lat, lon):
    la, lo = np.deg2rad(lat), np.deg2rad(lon)
    return np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]


def distances(e, lat, lon):
    """Distance (km) of each cell to the nearest station active each year, (years, cells)."""
    st = stations(e)
    cells = xyz(lat, lon)
    out = np.full((len(YEARS), lat.size), np.nan, np.float32)
    for k, y in enumerate(YEARS):
        s = st[(st.start <= y) & (st.stop >= y)]
        d, _ = cKDTree(xyz(s.lat.values, s.lon.values)).query(cells)
        out[k] = 2 * 6371 * np.arcsin(np.minimum(d / 2, 1))
    return out


def period(x, years, p):
    """Mean over the years of p, NaN if fewer than MIN_DAYS of them."""
    sel = (years >= p[0]) & (years <= p[1])
    v = x[sel]
    n = np.isfinite(v).sum(0)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.where(n >= MIN_DAYS * sel.sum(), np.nanmean(v, 0), np.nan)


def show(ax, field, lat, lon, title, vmax, cmap="RdBu_r", vmin=None, label="K"):
    vmin = -vmax if vmin is None else vmin
    im = ax.pcolormesh(lon, lat, field, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest", rasterized=True)
    ax.set_title(title, fontsize=10)
    ax.set_aspect(1 / np.cos(np.deg2rad(50)))
    ax.set_xlim(-25, 45.5)
    ax.set_ylim(25, 71.5)
    ax.set_facecolor("#e8e8e8")
    ax.tick_params(labelsize=7)
    plt.colorbar(im, ax=ax, shrink=0.75, label=label)


def report():
    ds = xr.open_mfdataset(sorted((OUT / "annees").glob("*.nc")), combine="nested", concat_dim="year").load()
    years = np.array(list(YEARS))
    days = np.array([xr.open_dataset(OUT / "annees" / f"{y}.nc").attrs["days"] for y in YEARS])
    lat, lon = ds.latitude.values, ds.longitude.values
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    land = (ds.n_tx.values[0] >= 0)
    cal = (years >= CAL[0]) & (years <= CAL[1])
    lines = [f"E-OBS v33.0e (moyenne d'ensemble, 0,1 deg, 4 voisins) - ERA5-Land, Tx et Tn journaliers",
             f"Mailles terre ERA5-Land dans le domaine E-OBS : {land.sum()}", ""]

    # (c) completeness.
    frac = {e: np.where(land, ds[f"n_{e}"].values[cal].clip(0).sum(0) / days[cal].sum(), np.nan) for e in FIELDS}
    full = {e: frac[e] >= COMPLETE for e in FIELDS}
    reg = {r: land & (LAT >= s) & (LAT <= n) & (LON >= w) & (LON <= east)
           for r, (s, n, w, east) in REGIONS.items()}
    reg_all = {"Domaine": land} | reg
    lines.append(f"(c) Completude E-OBS {CAL[0]}-{CAL[1]} : part des mailles terre ERA5-Land selon la part "
                 "des jours ou E-OBS existe (4 voisins valides)")
    lines.append(f"{'region':32s} {'mailles':>8s}   Tx: >=99 % >=95 % >=80 %   >0 %  |  Tn: >=99 % >=95 % >=80 %   >0 %")
    for r, m in reg_all.items():
        row = f"{r:32s} {m.sum():8d}  "
        for e in FIELDS:
            f = frac[e][m]
            row += "  " + " ".join(f"{100 * (f >= t).mean():6.1f}" for t in (0.99, 0.95, 0.8)) + f" {100 * (f > 0).mean():6.1f}  |"
        lines.append(row.rstrip("|"))
    first = {}
    for e in FIELDS:
        cov = ds[f"n_{e}"].values / days[:, None, None] >= COMPLETE
        # first year from which every year is covered
        tail = np.flip(np.cumprod(np.flip(cov, 0), 0), 0).astype(bool)
        first[e] = np.where(tail.any(0), years[np.argmax(tail, 0)], np.nan)
        first[e][~land] = np.nan
    lines.append("")

    fig, axes = plt.subplots(2, 2, figsize=(13, 9.5))
    for k, e in enumerate(FIELDS):
        show(axes[k, 0], 100 * frac[e], lat, lon, f"{e.capitalize()} : part des jours avec E-OBS, {CAL[0]}-{CAL[1]}",
             100, cmap="viridis", vmin=0, label="%")
        f = first[e].copy()
        f[land & np.isnan(f)] = 2026
        show(axes[k, 1], f, lat, lon, f"{e.capitalize()} : premiere annee couverte (>= {COMPLETE:.0%} des jours) "
             "jusqu'en 2025 ; 2026 = jamais", 2026, cmap="viridis", vmin=1970, label="annee")
    fig.tight_layout()
    fig.savefig(OUT / "c_completude.png", dpi=110)
    plt.close(fig)

    # (a) maps.
    d = {e: ds[f"d_{e}"].values for e in FIELDS}  # (year, season, lat, lon)
    ext = {e: ds[f"d_{EXTREME[e][0]}"].values for e in FIELDS}
    fig, axes = plt.subplots(2, 4, figsize=(20, 9))
    for k, e in enumerate(FIELDS):
        for s, name in enumerate(SEASONS):
            show(axes[k, s], period(d[e][:, s], years, CAL), lat, lon,
                 f"{e.capitalize()} {name}, E-OBS - ERA5-Land, {CAL[0]}-{CAL[1]}", 4)
    fig.tight_layout()
    fig.savefig(OUT / "a_saisons.png", dpi=110)
    plt.close(fig)

    annual = {e: d[e].mean(1) for e in FIELDS}  # NaN if a season is missing
    fig, axes = plt.subplots(2, 2, figsize=(13, 9.5))
    for k, e in enumerate(FIELDS):
        drift = period(annual[e], years, HALVES[1]) - period(annual[e], years, HALVES[0])
        show(axes[k, 0], drift, lat, lon, f"{e.capitalize()} annuel : derive de l'ecart, "
             f"{HALVES[1][0]}-{HALVES[1][1]} moins {HALVES[0][0]}-{HALVES[0][1]}", 1.5)
        name = EXTREME[e][0].upper()
        show(axes[k, 1], period(ext[e], years, CAL), lat, lon,
             f"{name}, E-OBS - ERA5-Land, moyenne {CAL[0]}-{CAL[1]}", 8)
    fig.tight_layout()
    fig.savefig(OUT / "a_derive_extremes.png", dpi=110)
    plt.close(fig)

    lines.append(f"(a) Ecart E-OBS - ERA5-Land (K), mailles completes a >= {COMPLETE:.0%} sur {CAL[0]}-{CAL[1]}, "
                 "moyenne sur les mailles ; derive = 2e moitie - 1re ; tendance par decennie sur "
                 f"{CAL[0]}-{CAL[1]} (moindres carres sur la serie annuelle de la region)")
    series = {}
    for e in FIELDS:
        lines.append(f"\n{e.capitalize()}")
        lines.append(f"{'region':32s} {'mailles':>7s} {'annee':>6s} {'DJF':>6s} {'MAM':>6s} {'JJA':>6s} {'SON':>6s} "
                     f"{EXTREME[e][0].upper():>6s} {'1970-90':>7s} {'1991-14':>7s} {'derive':>6s} {'tend.':>6s} {'2015-25':>7s}")
        for r, m in reg_all.items():
            m = m & full[e]
            if m.sum() < 20:
                lines.append(f"{r:32s} {m.sum():7d}  (trop peu de mailles)")
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                yr = np.nanmean(annual[e][:, m], 1)
                ys = np.nanmean(d[e][:, :, m], 2)
                ye = np.nanmean(ext[e][:, m], 1)
            series[(e, r)] = yr
            c = cal
            h0 = (years >= HALVES[0][0]) & (years <= HALVES[0][1])
            h1 = (years >= HALVES[1][0]) & (years <= HALVES[1][1])
            trend = 10 * np.polyfit(years[c], yr[c], 1)[0]
            lines.append(f"{r:32s} {m.sum():7d} {yr[c].mean():+6.2f} "
                         + " ".join(f"{ys[c, s].mean():+6.2f}" for s in range(4))
                         + f" {ye[c].mean():+6.2f} {yr[h0].mean():+7.2f} {yr[h1].mean():+7.2f} "
                           f"{yr[h1].mean() - yr[h0].mean():+6.2f} {trend:+6.2f} {yr[~(years <= CAL[1])].mean():+7.2f}")
    lines.append("")

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5), sharey=True)
    for k, e in enumerate(FIELDS):
        ax = axes[k]
        for r in ["Domaine"] + list(REGIONS):
            if (e, r) in series:
                ax.plot(years, series[(e, r)], lw=2.2 if r == "Domaine" else 1.2,
                        color="black" if r == "Domaine" else None, label=r)
        ax.axvline(CAL[1] + 0.5, color="grey", ls="--", lw=0.8)
        ax.axhline(0, color="grey", lw=0.5)
        ax.set_title(f"{e.capitalize()} annuel, E-OBS - ERA5-Land, mailles completes a >= {COMPLETE:.0%}", fontsize=10)
        ax.set_ylabel("K")
        ax.grid(alpha=0.3)
    axes[1].legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "a_series.png", dpi=110)
    plt.close(fig)

    # (b) distance to the nearest station.
    lines.append("(b) Ecart selon la distance a la station d'entree E-OBS la plus proche, active l'annee "
                 "(moyenne de la distance sur la periode), mailles terre du domaine (sans filtre de completude) ; "
                 "moyenne sur les mailles et dispersion entre mailles (ecart-type)")
    cells = np.flatnonzero(land.ravel())
    dist = {e: distances(e, LAT.ravel()[cells], LON.ravel()[cells]) for e in FIELDS}
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for k, e in enumerate(FIELDS):
        s_main = 2 if e == "tx" else 0  # JJA for Tx, DJF for Tn
        lines.append(f"\n{e.capitalize()} : annee | {list(SEASONS)[s_main]}")
        lines.append(f"{'periode':10s} {'km':>10s} {'mailles':>8s} {'annee':>7s} {'e.-t.':>6s} "
                     f"{list(SEASONS)[s_main]:>7s} {'e.-t.':>6s}")
        for p in HALVES:
            sel = (years >= p[0]) & (years <= p[1])
            dd = np.nanmean(dist[e][sel], 0)
            ya = period(annual[e], years, p).ravel()[cells]
            ys = period(d[e][:, s_main], years, p).ravel()[cells]
            means = []
            for lo, hi in zip(DISTANCES[:-1], DISTANCES[1:]):
                b = (dd >= lo) & (dd < hi) & np.isfinite(ya)
                if b.sum() < 20:
                    means.append(np.nan)
                    continue
                means.append(ys[b & np.isfinite(ys)].mean())
                lines.append(f"{p[0]}-{p[1]} {lo:4d}-{hi:<5d} {b.sum():8d} {ya[b].mean():+7.2f} {ya[b].std():6.2f} "
                             f"{np.nanmean(ys[b]):+7.2f} {np.nanstd(ys[b]):6.2f}")
            axes[k].plot(range(len(means)), means, "o-", label=f"{p[0]}-{p[1]}")
        # drift against change of distance
        dd0 = np.nanmean(dist[e][(years >= HALVES[0][0]) & (years <= HALVES[0][1])], 0)
        dd1 = np.nanmean(dist[e][(years >= HALVES[1][0]) & (years <= HALVES[1][1])], 0)
        drift = (period(annual[e], years, HALVES[1]) - period(annual[e], years, HALVES[0])).ravel()[cells]
        lines.append(f"Derive annuelle (2e - 1re moitie) selon la distance en 1re moitie -> 2e moitie")
        for name, b in (("station deja proche (< 25 km les deux)", (dd0 < 25) & (dd1 < 25)),
                        ("rapprochee (>= 25 km -> < 25 km)", (dd0 >= 25) & (dd1 < 25)),
                        ("lointaine les deux (>= 25 km)", (dd0 >= 25) & (dd1 >= 25)),
                        ("eloignee (< 25 km -> >= 25 km)", (dd0 < 25) & (dd1 >= 25))):
            b = b & np.isfinite(drift)
            if b.sum():
                lines.append(f"  {name:40s} {b.sum():7d} mailles  {drift[b].mean():+6.2f} K "
                             f"(e.-t. {drift[b].std():.2f})")
        labels = [f"{lo}-{hi}" for lo, hi in zip(DISTANCES[:-1], DISTANCES[1:])]
        axes[k].set_xticks(range(len(labels)), labels)
        axes[k].set_xlabel("distance a la station la plus proche (km)")
        axes[k].set_ylabel("K")
        axes[k].axhline(0, color="grey", lw=0.5)
        axes[k].set_title(f"{e.capitalize()} {list(SEASONS)[s_main]}, E-OBS - ERA5-Land, moyenne sur les mailles",
                          fontsize=10)
        axes[k].legend()
        axes[k].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "b_distance.png", dpi=110)
    plt.close(fig)
    nst = {e: [int((lambda s: ((s.start <= y) & (s.stop >= y)).sum())(stations(e))) for y in (1970, 1990, 2014, 2025)]
           for e in FIELDS}
    lines.append("\nStations actives (domaine entier) en 1970, 1990, 2014, 2025 : "
                 + " ; ".join(f"{e} {nst[e]}" for e in FIELDS))

    (OUT / "eobs_land.log").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def network():
    """One dot per E-OBS input station (Tx) active in a few years."""
    st = stations("tx")
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    for ax, y in zip(axes.ravel(), (1970, 1990, 2014, 2025)):
        s = st[(st.start <= y) & (st.stop >= y)]
        ax.scatter(s.lon, s.lat, s=1.5, color="#2a78d6", lw=0)
        ax.set_title(f"Stations Tx d'entree E-OBS v33.0e actives en {y} : {len(s)}", fontsize=10)
        ax.set_aspect(1 / np.cos(np.deg2rad(50)))
        ax.set_xlim(-25, 45.5)
        ax.set_ylim(25, 71.5)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "stations.png", dpi=120)
    plt.close(fig)


def density():
    """Gap 1991-2014 against local station density and altitude.

    Per cell: stations active in 2000 within 25 km, E-OBS altitude of the cell
    (mean of the 4 neighbours), mean altitude of those stations minus the cell's.
    """
    ds = xr.open_mfdataset(sorted((OUT / "annees").glob("*.nc")), combine="nested", concat_dim="year").load()
    years = np.array(list(YEARS))
    p = HALVES[1]
    lat, lon = ds.latitude.values, ds.longitude.values
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    grid = Grid()
    elev = xr.open_dataset(EOBS / "elev_ens_0.1deg_reg_v33.0e.nc").elevation.values
    alt = grid.mean4(elev[None])[0]
    gaps = {"Tn DJF": period(ds.d_tn.values[:, 0], years, p), "Tx JJA": period(ds.d_tx.values[:, 2], years, p),
            "TNn": period(ds.d_tnn.values, years, p), "TXx": period(ds.d_txx.values, years, p)}
    ok = np.isfinite(alt) & np.all([np.isfinite(g) for g in gaps.values()], 0) & (LAT >= 35)
    st = stations("tx")
    raw = pd.read_csv(STATIONS / "stations_info_tx_v33.0e.txt", sep="|", skipinitialspace=True)
    st["elev"] = raw.iloc[:, 5].astype(float).values
    st = st[(st.start <= 2000) & (st.stop >= 2000) & (st.elev > -100)]
    tree = cKDTree(xyz(st.lat.values, st.lon.values))
    r = 2 * np.sin(25 / 6371 / 2)
    near = tree.query_ball_point(xyz(LAT[ok], LON[ok]), r)
    n = np.array([len(x) for x in near])
    salt = np.array([st.elev.values[x].mean() if x else np.nan for x in near])
    a = alt[ok]
    dz = salt - a
    g = {k: v[ok] for k, v in gaps.items()}

    lines = [f"Ecart E-OBS - ERA5-Land {p[0]}-{p[1]} (K) selon la densite locale de stations Tx (actives en 2000, "
             f"rayon 25 km) et l'altitude E-OBS de la maille ; mailles terre au nord de 35 N : {ok.sum()}",
             "Moyenne | ecart quadratique entre mailles (RMS), par grandeur", ""]
    head = f"{'':28s} {'mailles':>8s} " + " ".join(f"{k:>14s}" for k in g)

    def table(title, classes):
        lines.append(title)
        lines.append(head)
        for name, m in classes:
            if m.sum() < 30:
                continue
            lines.append(f"{name:28s} {m.sum():8d} " + " ".join(
                f"{v[m].mean():+6.2f} | {np.sqrt((v[m] ** 2).mean()):5.2f}" for v in g.values()))
        lines.append("")

    dens = [("0 station", n == 0), ("1 station", n == 1), ("2-3 stations", (n >= 2) & (n <= 3)),
            ("4-7 stations", (n >= 4) & (n <= 7)), (">= 8 stations", n >= 8)]
    alts = [("< 300 m", a < 300), ("300-700 m", (a >= 300) & (a < 700)), ("700-1200 m", (a >= 700) & (a < 1200)),
            ("1200-1800 m", (a >= 1200) & (a < 1800)), (">= 1800 m", a >= 1800)]
    table("Par densite de stations, toutes altitudes", dens)
    table("Par altitude, toutes densites", alts)
    for an, am in alts[2:]:
        table(f"Altitude {an}, par densite", [(dn, dm & am) for dn, dm in dens])
    dzc = [("stations > 300 m plus bas", dz < -300), ("stations 100-300 m plus bas", (dz >= -300) & (dz < -100)),
           ("a +- 100 m", (dz >= -100) & (dz <= 100)), ("stations > 100 m plus haut", dz > 100)]
    table("Altitude >= 700 m avec au moins 1 station a 25 km, par altitude des stations - maille",
          [(k, m & (a >= 700)) for k, m in dzc])
    with np.errstate(invalid="ignore"):
        cor = {k: np.corrcoef(v[n > 0], dz[n > 0])[0, 1] for k, v in g.items()}
    lines.append("Correlation entre mailles (au moins 1 station a 25 km) de l'ecart avec l'altitude des stations "
                 "- maille : " + ", ".join(f"{k} {c:+.2f}" for k, c in cor.items()))
    (OUT / "densite.log").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    nmap = np.full(alt.shape, np.nan)
    nmap[ok] = n
    fig, axes = plt.subplots(1, 4, figsize=(22, 5.2))
    box = (4.5, 17.5, 43.3, 48.7)
    for ax, (field, title, vmax, cmap, vmin) in zip(axes, (
            (nmap, "Stations Tx actives en 2000 a 25 km", 15, "viridis", 0),
            (alt, "Altitude E-OBS de la maille (m)", 3000, "terrain", 0),
            (np.where(ok, gaps["Tn DJF"], np.nan), f"Tn DJF, E-OBS - ERA5-Land, {p[0]}-{p[1]}", 5, "RdBu_r", None),
            (np.where(ok, gaps["Tx JJA"], np.nan), f"Tx JJA, E-OBS - ERA5-Land, {p[0]}-{p[1]}", 5, "RdBu_r", None))):
        show(ax, field, lat, lon, title, vmax, cmap=cmap, vmin=vmin, label="")
        ax.set_xlim(box[0], box[1])
        ax.set_ylim(box[2], box[3])
        ax.scatter(st.lon, st.lat, s=1, color="black", lw=0)
    fig.tight_layout()
    fig.savefig(OUT / "densite_alpes.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    {"compute": compute, "report": report, "stations": network, "densite": density}[sys.argv[1]]()
