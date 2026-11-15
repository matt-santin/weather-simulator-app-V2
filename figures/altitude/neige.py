"""Neige au sol avec les températures ramenées à l'altitude de la station (suite de figures/neige/altitude.py).

    PYTHONPATH=. python figures/altitude/neige.py            (après figures/altitude/temperatures.py ; 1 min)

Même calcul que le site (0,5 °C, 4 mm, 2 mm), mêmes stations de neige (data/neige), contrôle sur les hivers
2001-2020. tas est ramené à l'altitude de la station : sans correction, 5 K/km, et gradient par mois
(moyenne des gradients de Tx et de Tn de data/altitude/gradients.npy). Altitude des mailles : celle du
stockage (Store.elevation), et non plus la maille E-OBS la plus proche.
"""
import numpy as np

from src.app.store import Store
from src.config import ROOT

st = np.load(ROOT / "data" / "neige" / "stations.npz")
m = np.load(ROOT / "data" / "neige" / "meteo.npz")
G = np.load(ROOT / "data" / "altitude" / "gradients.npy").mean(1)   # K/km, par mois
p = m["pick"]
sd = st["sd"][p].T
tas0, pr = m["tas"].T, m["pr"].T
alt, name = st["alt"][p].astype(float), st["name"][p]
s = Store()
zc = np.array([s.elevation(s.cell(float(la), float(lo))) or np.nan for la, lo in zip(st["lat"][p], st["lon"][p])], float)
dz = zc - alt
days = np.arange("1970-07-01", "2020-07-01", dtype="datetime64[D]")
month = days.astype("datetime64[M]").astype(int) % 12 + 1
first = days.astype("datetime64[M]").astype("datetime64[D]") == days
winter = (days.astype("datetime64[Y]").astype(int) + 1970) + (month >= 7)
season = np.isin(month, (11, 12, 1, 2, 3, 4))
W = np.arange(1971, 2021)
VAL = W > 2000
valid, obs = sd >= 0, sd >= 1


def swe(tas, ts=0.5, ddf=4.0):
    x = np.zeros(tas.shape[1], "float32")
    out = np.empty(tas.shape, "float32")
    fall, melt = np.where(tas < ts, pr, 0.0), ddf * np.maximum(tas, 0.0)
    for k in range(tas.shape[0]):
        if first[k] and month[k] == 8:
            x[:] = 0
        x = np.maximum(x + fall[k] - melt[k], 0.0)
        out[k] = x
    return out


def per_winter(flag):
    out = np.full((W.size, sd.shape[1]), np.nan)
    for i, w in enumerate(W):
        rows = season & (winter == w)
        n = valid[rows].sum(0)
        full = n >= 0.95 * rows.sum()
        out[i, full] = (flag[rows] & valid[rows]).sum(0)[full] * rows.sum() / n[full]
    return out


O = per_winter(obs)
val = (np.isfinite(O[VAL]).sum(0) >= 10) & np.isfinite(dz)
d = np.where(np.isfinite(dz), dz, 0.0)[None, :] / 1000.0
runs = {"sans correction": per_winter(swe(tas0) >= 2.0),
        "5 K/km": per_winter(swe(tas0 + 5.0 * d) >= 2.0),
        "par mois": per_winter(swe(tas0 + G[month - 1][:, None] * d) >= 2.0)}


def stats(M, sel):
    ok = np.isfinite(O[VAL][:, sel])
    mo, mm = np.nanmean(O[VAL][:, sel], 0), np.nanmean(np.where(ok, M[VAL][:, sel], np.nan), 0)
    return mo.mean(), mm.mean(), np.abs(mm - mo).mean()


def table(title, groups):
    print(f"\n{title}\n  {'':16s} {'st.':>4s} {'observé':>8s} | " + " | ".join(f"{k:>18s}" for k in runs))
    for label, sel in groups:
        k = sel & val
        if k.sum() < 2:
            continue
        print(f"  {label:16s} {k.sum():4d} {stats(runs['sans correction'], k)[0]:8.1f} | "
              + " | ".join(f"{stats(M, k)[1]:6.1f} (err {stats(M, k)[2]:4.1f})" for M in runs.values()))


print("gradient de tas par mois (K/km) : " + " ".join(f"{g:.1f}" for g in G))
print("Contrôle 2001-2020, jours de neige au sol par hiver : calculé (erreur absolue moyenne entre stations)")
table("Par altitude de la station", (("< 300 m", alt < 300), ("300-800 m", (alt >= 300) & (alt < 800)),
                                     ("800-1500 m", (alt >= 800) & (alt < 1500)), (">= 1500 m", alt >= 1500)))
table("Par altitude de la maille (critère du site)", (("maille <= 800 m", zc <= 800), ("maille > 800 m", zc > 800)))
table("Par écart d'altitude maille - station, toutes altitudes",
      [(f"{lo:+d} à {hi:+d} m", (dz >= lo) & (dz < hi)) for lo, hi in ((-3000, -300), (-300, -100), (-100, 100), (100, 300), (300, 3000))])
print("\nExemples : station / maille (m) ; observé | " + " | ".join(runs))
for want in ("SAENTIS", "BROCKEN", "LIORAN", "CHAMONIX", "PONTARLIER", "GRENOBLE", "DAVOS", "INNSBRUCK", "FELDBERG", "ZUGSPITZE"):
    for j in np.nonzero(np.char.find(np.char.upper(name.astype(str)), want) >= 0)[0][:2]:
        if val[j]:
            print(f"  {str(name[j])[:24]:24s} {alt[j]:5.0f} / {zc[j]:5.0f} ; {np.nanmean(O[VAL, j]):6.1f} | "
                  + " | ".join(f"{np.nanmean(np.where(np.isfinite(O[VAL, j]), M[VAL, j], np.nan)):6.1f}" for M in runs.values()))
