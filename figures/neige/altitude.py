"""Montagne : ramener la température de la maille à l'altitude de la station (gradient vertical), puis neige.
LaCie branché (altitude des mailles E-OBS à 0,1°).

    PYTHONPATH=. python figures/neige/altitude.py data/neige/stations.npz data/neige/meteo.npz
"""
import sys
import numpy as np, xarray as xr
from src.app.store import Store
st = np.load(sys.argv[1]); m = np.load(sys.argv[2]); p = m["pick"]
sd = st["sd"][p].T; tas0 = m["tas"].T; pr = m["pr"].T; alt = st["alt"][p].astype(float); name = st["name"][p]; cn = st["cn"][p]
s = Store(); el = xr.open_dataset("/Volumes/LaCie/weather-simulator-app-V2/data/eobs/0.1deg/elev_ens_0.1deg_reg_v33.0e.nc")
v = list(el.data_vars)[0]; E = el[v].squeeze()
zc = np.empty(p.size)
for k, (la, lo) in enumerate(zip(st["lat"][p], st["lon"][p])):
    plat, plon = s.position(s.cell(float(la), float(lo)))
    zc[k] = float(E.sel(latitude=plat, longitude=plon, method="nearest"))
dz = zc - alt   # maille plus haute que la station : positif
print(f"altitude de la maille moins altitude de la station : médiane {np.nanmedian(dz):+.0f} m ; au-dessus de 800 m : médiane {np.nanmedian(dz[alt >= 800]):+.0f} m, écart absolu médian {np.nanmedian(np.abs(dz[alt >= 800])):.0f} m")
days = np.arange("1970-07-01", "2020-07-01", dtype="datetime64[D]")
month = days.astype("datetime64[M]").astype(int) % 12 + 1
first = days.astype("datetime64[M]").astype("datetime64[D]") == days
winter = (days.astype("datetime64[Y]").astype(int) + 1970) + (month >= 7)
season = np.isin(month, (11, 12, 1, 2, 3, 4)); W = np.arange(1971, 2021); VAL = W > 2000
valid = sd >= 0; obs = sd >= 1
def swe(tas, ts=0.5, ddf=4.0):
    x = np.zeros(tas.shape[1], "float32"); out = np.empty(tas.shape, "float32")
    fall = np.where(tas < ts, pr, 0.0); melt = ddf * np.maximum(tas, 0.0)
    for k in range(tas.shape[0]):
        if first[k] and month[k] == 8: x[:] = 0
        x = np.maximum(x + fall[k] - melt[k], 0.0); out[k] = x
    return out
def per_winter(flag):
    out = np.full((W.size, sd.shape[1]), np.nan)
    for i, w in enumerate(W):
        rows = season & (winter == w); n = valid[rows].sum(0); full = n >= 0.95 * rows.sum()
        out[i, full] = (flag[rows] & valid[rows]).sum(0)[full] * rows.sum() / n[full]
    return out
O = per_winter(obs); val = (np.isfinite(O[VAL]).sum(0) >= 10) & np.isfinite(dz)
def stats(M, sel):
    ok = np.isfinite(O[VAL][:, sel]); mo, mm = np.nanmean(O[VAL][:, sel], 0), np.nanmean(np.where(ok, M[VAL][:, sel], np.nan), 0)
    yr = [np.corrcoef(O[VAL, j][np.isfinite(O[VAL, j])], M[VAL, j][np.isfinite(O[VAL, j])])[0, 1] for j in sel.nonzero()[0] if np.nanmean(O[VAL, j]) >= 5]
    return mo.mean(), mm.mean(), np.abs(mm - mo).mean(), (mm - mo).mean(), np.median(yr) if yr else float("nan")
bands = (("< 300 m", alt < 300), ("300-800 m", (alt >= 300) & (alt < 800)), ("800-1500 m", (alt >= 800) & (alt < 1500)), (">= 1500 m", alt >= 1500))
runs = {}
for g in (0.0, 5.0, 6.5):
    runs[g] = per_winter(swe(tas0 + g * dz[None, :] / 1000.0) >= 2.0)
print("\nContrôle 2001-2020, jours de neige au sol par hiver : observé, puis calculé (erreur absolue, corrélation entre hivers)")
print(f"  {'':11s} {'st.':>4s} {'observé':>8s} | {'sans correction':>24s} | {'gradient 5 K/km':>24s} | {'gradient 6,5 K/km':>24s}")
for label, sel in bands:
    k = sel & val
    if not k.any(): continue
    line = f"  {label:11s} {k.sum():4d} {stats(runs[0.0], k)[0]:8.1f} |"
    for g in (0.0, 5.0, 6.5):
        o, c, e, b, r = stats(runs[g], k); line += f" {c:6.1f} (err {e:4.1f}, r {r:4.2f}) |"
    print(line)
print("\nStations au-dessus de 800 m, par écart d'altitude maille - station :")
for lo, hi in ((-3000, -300), (-300, -100), (-100, 100), (100, 300), (300, 3000)):
    k = val & (alt >= 800) & (dz >= lo) & (dz < hi)
    if k.sum() == 0: continue
    a, b = stats(runs[0.0], k), stats(runs[6.5], k)
    print(f"  {lo:+5d} à {hi:+5d} m : {k.sum():2d} st., observé {a[0]:5.1f} ; sans correction {a[1]:5.1f} (err {a[2]:4.1f}) ; avec 6,5 K/km {b[1]:5.1f} (err {b[2]:4.1f})")
print("\nQuelques stations de montagne (altitude station / maille) : observé ; sans correction ; avec 6,5 K/km")
for j in np.argsort(-alt):
    if not val[j] or alt[j] < 800: continue
    o = np.nanmean(O[VAL, j]); ok = np.isfinite(O[VAL, j])
    print(f"  {name[j][:26]:26s} {cn[j]} {alt[j]:5.0f} / {zc[j]:5.0f} m : {o:5.1f} ; {np.nanmean(runs[0.0][VAL, j][ok]):5.1f} ; {np.nanmean(runs[6.5][VAL, j][ok]):5.1f}")
    if (alt[val & (alt >= 800)] >= alt[j]).sum() >= 22: break
