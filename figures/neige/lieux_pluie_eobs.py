"""Les mêmes lieux avec la pluie d'E-OBS dans les données passées, face au modèle corrigé. LaCie branché.

    PYTHONPATH=. python figures/neige/lieux_pluie_eobs.py
"""
from datetime import date
import numpy as np, xarray as xr
from src.app.store import Store
s = Store()
places = [("Lyon", 45.75, 4.85), ("Strasbourg", 48.58, 7.75), ("Besançon", 47.24, 6.02), ("Grenoble", 45.19, 5.72), ("Berlin", 52.52, 13.40),
          ("Munich", 48.14, 11.58), ("Pontarlier", 46.90, 6.35), ("Oslo", 59.91, 10.75)]
ds = xr.open_dataset("/Volumes/LaCie/weather-simulator-app-V2/data/eobs/rr_ens_mean_0.25deg_reg_v33.0e.nc")
def eobs(lat, lon, a, b):
    return ds.rr.sel(latitude=lat, longitude=lon, method="nearest").sel(time=slice(a.isoformat(), b.isoformat())).values
def run(tas, pr, a, n, ts, ddf, s0):
    d = np.arange(np.datetime64(a.isoformat()), np.datetime64(a.isoformat()) + np.timedelta64(tas.size, "D"))
    month = d.astype("datetime64[M]").astype(int) % 12 + 1; day1 = (month == 8) & (d.astype("datetime64[M]").astype("datetime64[D]") == d)
    swe = 0.0; flag = np.zeros(tas.size, bool)
    for k in range(tas.size):
        if day1[k]: swe = 0.0
        swe = max(swe + (pr[k] if tas[k] < ts else 0.0) - ddf * max(tas[k], 0.0), 0.0); flag[k] = swe >= s0
    cold = np.isin(month, (11, 12, 1, 2, 3, 4))
    return flag[cold].sum() / n, ((tas[cold] < 0.5) & (pr[cold] >= 1)).sum() / n, (pr[cold] >= 1).sum() / n
A, B = (0.5, 4.0, 2.0), (0.5, 3.0, 1.0)   # réglage calé avec la pluie d'ERA5, avec celle d'E-OBS
print("Jours de neige au sol par hiver, 1971-2000 puis 1991-2020")
print(f"{'':11s} | réglage ERA5 : passé(ERA5) modèle | réglage E-OBS : passé(E-OBS) modèle || 1991-2020 : passé(ERA5) passé(E-OBS) modèle(A) modèle(B)")
diag = []
for name, lat, lon in places:
    c = s.cell(lat, lon); out = {}
    for y0, y1 in ((1971, 2000), (1991, 2020)):
        a, b = date(y0 - 1, 8, 1), date(y1, 7, 31); n = y1 - y0 + 1
        past = s.values("era5", c, a, b, ("tas", "pr")); mod = s.values("cordex", c, a, b, ("tas", "pr"))
        rr = eobs(lat, lon, a, b); rr = np.where(np.isnan(rr), past["pr"], rr)
        out[y0] = (run(past["tas"], past["pr"], a, n, *A), run(mod["tas"], mod["pr"], a, n, *A), run(past["tas"], rr, a, n, *B), run(mod["tas"], mod["pr"], a, n, *B))
    o, q = out[1971], out[1991]
    print(f"{name:11s} |                {o[0][0]:6.1f} {o[1][0]:6.1f} |                  {o[2][0]:6.1f} {o[3][0]:6.1f} ||             {q[0][0]:6.1f} {q[2][0]:11.1f} {q[1][0]:9.1f} {q[3][0]:9.1f}")
    diag.append((name, o))
print("\n1971-2000, novembre à avril, par hiver : jours à 1 mm ou plus, puis jours froids et humides ; passé ERA5 / passé E-OBS / modèle")
for name, o in diag:
    print(f"{name:11s} jours humides {o[0][2]:5.1f} / {o[2][2]:5.1f} / {o[1][2]:5.1f}   froids et humides {o[0][1]:5.1f} / {o[2][1]:5.1f} / {o[1][1]:5.1f}")
