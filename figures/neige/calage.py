"""Calage du degré-jour sur les hivers 1971-2000, contrôle sur 2001-2020.

    python figures/neige/calage.py data/neige/stations.npz data/neige/meteo.npz data/neige/reglage.npy
"""
import sys, itertools
import numpy as np
st = np.load(sys.argv[1]); m = np.load(sys.argv[2]); p = m["pick"]
sd = st["sd"][p].T; tas, pr = m["tas"].T, m["pr"].T
alt, cn, name = st["alt"][p], st["cn"][p], st["name"][p]
days = np.arange("1970-07-01", "2020-07-01", dtype="datetime64[D]")
month = days.astype("datetime64[M]").astype(int) % 12 + 1
first = days.astype("datetime64[M]").astype("datetime64[D]") == days
winter = (days.astype("datetime64[Y]").astype(int) + 1970) + (month >= 7)
season = np.isin(month, (11, 12, 1, 2, 3, 4))
W = np.arange(1971, 2021); CAL, VAL = W <= 2000, W > 2000
valid = sd >= 0; obs = sd >= 1

def swe(ts, ddf):
    s = np.zeros(tas.shape[1], "float32"); out = np.empty(tas.shape, "float32")
    fall = np.where(tas < ts, pr, 0.0); melt = ddf * np.maximum(tas, 0.0)
    for k in range(tas.shape[0]):
        if first[k] and month[k] == 8: s[:] = 0
        s = np.maximum(s + fall[k] - melt[k], 0.0); out[k] = s
    return out

def per_winter(flag):
    out = np.full((W.size, sd.shape[1]), np.nan)
    for i, w in enumerate(W):
        rows = season & (winter == w); n = valid[rows].sum(0); full = n >= 0.95 * rows.sum()
        out[i, full] = (flag[rows] & valid[rows]).sum(0)[full] * rows.sum() / n[full]
    return out

O = per_winter(obs)
cal = np.isfinite(O[CAL]).sum(0) >= 15; val = np.isfinite(O[VAL]).sum(0) >= 10
print(f"calage 1971-2000 : {cal.sum()} stations ; contrôle 2001-2020 : {val.sum()} stations ; les deux : {(cal & val).sum()}")
import collections; print("pays (calage) :", collections.Counter(cn[cal]).most_common(8))
def score(M, rows, sel):
    both = np.isfinite(O[rows][:, sel])
    mo, mm = np.nanmean(O[rows][:, sel], 0), np.nanmean(np.where(both, M[rows][:, sel], np.nan), 0)
    return np.mean(np.abs(mm - mo)), np.mean(mm - mo), np.corrcoef(mm, mo)[0, 1], mo.mean(), mm.mean()
res = []
for ts, ddf, s0 in itertools.product((0.5, 1.0, 1.5, 2.0), (1.5, 2.0, 3.0, 4.0, 5.0), (1.0, 2.0, 5.0)):
    M = per_winter(swe(ts, ddf) >= s0)
    res.append((score(M, CAL, cal), score(M, VAL, val), ts, ddf, s0))
res.sort(key=lambda r: r[0][0])
print("\nRéglages classés par erreur sur 1971-2000 (jours par hiver) ; à droite, les mêmes sur 2001-2020, non vus au calage :")
print("  Ts   DDF  S0 | 1971-2000 : erreur  biais  corr. | 2001-2020 : erreur  biais  corr.")
for c, v, ts, ddf, s0 in res[:6] + [r for r in res if (r[2], r[3], r[4]) == (1.5, 3.0, 5.0)]:
    print(f"  {ts:3.1f}  {ddf:3.1f}  {s0:2.0f} |             {c[0]:5.1f}  {c[1]:+5.1f}  {c[2]:.3f} |             {v[0]:5.1f}  {v[1]:+5.1f}  {v[2]:.3f}")
_, _, ts, ddf, s0 = res[0]
np.save(sys.argv[3], np.array([ts, ddf, s0]))
snow = swe(ts, ddf) >= s0; M = per_winter(snow)
print(f"\nRéglage retenu : neige si tas < {ts} °C, fonte {ddf} mm par °C et par jour, neige au sol dès {s0:.0f} mm d'eau")
print("Contrôle sur 2001-2020, par tranche d'altitude (jours de neige au sol par hiver) :")
for label, sel in (("< 300 m", alt < 300), ("300-800 m", (alt >= 300) & (alt < 800)), ("800-1500 m", (alt >= 800) & (alt < 1500)), (">= 1500 m", alt >= 1500)):
    k = sel & val
    if not k.any(): continue
    e, b, r, mo, mm = score(M, VAL, k)
    idx = k.nonzero()[0]; yr = []
    for j in idx:
        ok = np.isfinite(O[VAL, j])
        if np.nanmean(O[VAL, j]) >= 5 and ok.sum() >= 10: yr.append(np.corrcoef(O[VAL, j][ok], M[VAL, j][ok])[0, 1])
    print(f"  {label:11s} {k.sum():4d} stations : observé {mo:5.1f}, calculé {mm:5.1f}, erreur abs. {e:4.1f}, biais {b:+5.1f}, corr. entre hivers (médiane) {np.median(yr) if yr else float('nan'):.2f}")
# la tendance observée est-elle reproduite ?
both = cal & val
d_obs = np.nanmean(O[VAL][:, both], 0) - np.nanmean(O[CAL][:, both], 0)
Mm = np.where(np.isfinite(O), M, np.nan); d_mod = np.nanmean(Mm[VAL][:, both], 0) - np.nanmean(Mm[CAL][:, both], 0)
print(f"\nChangement 2001-2020 moins 1971-2000, {both.sum()} stations : observé {d_obs.mean():+.1f} jours, calculé {d_mod.mean():+.1f} jours, corrélation entre stations {np.corrcoef(d_obs, d_mod)[0,1]:.2f}")
