"""Pluie d'E-OBS (0,25°) aux stations, 1970-07-01 .. 2020-06-30, et altitude de la maille. LaCie branché.

    python figures/neige/lire_pluie_eobs.py data/neige/stations.npz data/neige/meteo.npz data/neige/pluie_eobs.npz
"""
import sys, time
import numpy as np, xarray as xr
E = "/Volumes/LaCie/weather-simulator-app-V2/data/eobs/"
st = np.load(sys.argv[1]); m = np.load(sys.argv[2]); p = m["pick"]
lat, lon = st["lat"][p], st["lon"][p]
ds = xr.open_dataset(E + "rr_ens_mean_0.25deg_reg_v33.0e.nc")
print(ds.rr.dims, ds.rr.shape, ds.rr.attrs.get("units"), float(ds.latitude[0]), float(ds.latitude[1]), float(ds.longitude[0]))
i = np.abs(ds.latitude.values[:, None] - lat[None]).argmin(0); j = np.abs(ds.longitude.values[:, None] - lon[None]).argmin(0)
print("écart max à la maille (deg) :", float(np.abs(ds.latitude.values[i] - lat).max()), float(np.abs(ds.longitude.values[j] - lon).max()))
days = np.arange("1970-07-01", "2020-07-01", dtype="datetime64[D]")
out = np.full((p.size, days.size), np.nan, "float32"); t = time.time()
for y in range(1970, 2021):
    a, b = max(np.datetime64(f"{y}-01-01"), days[0]), min(np.datetime64(f"{y}-12-31"), days[-1])
    block = ds.rr.sel(time=slice(a, b)).values          # (jours, lat, lon)
    k0 = (a - days[0]).astype(int); out[:, k0:k0 + block.shape[0]] = block[:, i, j].T
print(f"lu en {time.time()-t:.0f} s ; jours manquants {np.isnan(out).mean():.2%} ; stations avec plus de 1 % de lacunes : {(np.isnan(out).mean(1) > 0.01).sum()}")
el = xr.open_dataset(E + "elev_ens_0.25deg_reg_v33.0e.nc"); v = [n for n in el.data_vars][0]
elev = el[v].values[i, j] if el[v].ndim == 2 else el[v].values[0][i, j]
np.savez_compressed(sys.argv[3], rr=out, elev=elev.astype("float32"))
