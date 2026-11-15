"""Neige au sol : pluie d'ERA5 (celle du site) contre pluie d'E-OBS, températures inchangées.

    python figures/neige/pluie_eobs.py data/neige/stations.npz data/neige/meteo.npz data/neige/pluie_eobs.npz data/neige/reglages_pluie.npy
"""
import sys, itertools
import numpy as np
st = np.load(sys.argv[1]); m = np.load(sys.argv[2]); r = np.load(sys.argv[3]); p = m["pick"]
good = np.isnan(r["rr"]).mean(1) <= 0.01
sd = st["sd"][p][good].T; tas = m["tas"][good].T; era = m["pr"][good].T
rr = r["rr"][good].T; rr = np.where(np.isnan(rr), era, rr)
alt = st["alt"][p][good]
print(f"{good.sum()} stations où E-OBS a la pluie (au plus 1 % de lacunes, comblées par ERA5)")
days = np.arange("1970-07-01", "2020-07-01", dtype="datetime64[D]")
month = days.astype("datetime64[M]").astype(int) % 12 + 1
first = days.astype("datetime64[M]").astype("datetime64[D]") == days
winter = (days.astype("datetime64[Y]").astype(int) + 1970) + (month >= 7)
season = np.isin(month, (11, 12, 1, 2, 3, 4)); W = np.arange(1971, 2021); CAL, VAL = W <= 2000, W > 2000
valid = sd >= 0; obs = sd >= 1
nw = 50.0
print("\nLes deux pluies aux stations, novembre à avril, par hiver (moyenne des stations) :")
print(f"  {'':34s} ERA5   E-OBS")
for label, f in (("jours à 1 mm ou plus", lambda x: (x[season] >= 1).sum(0) / nw), ("cumul (mm)", lambda x: x[season].sum(0) / nw),
                 ("jours de bruine (0,1 à 1 mm)", lambda x: ((x[season] >= 0.1) & (x[season] < 1)).sum(0) / nw),
                 ("jours froids (< 0,5 °C) et humides", lambda x: ((x[season] >= 1) & (tas[season] < 0.5)).sum(0) / nw),
                 ("pluie tombée par temps froid (mm)", lambda x: np.where(tas[season] < 0.5, x[season], 0).sum(0) / nw)):
    print(f"  {label:34s} {f(era).mean():6.1f} {f(rr).mean():6.1f}")
both_wet = ((era[season] >= 1) & (rr[season] >= 1)).sum() / ((era[season] >= 1) | (rr[season] >= 1)).sum()
print(f"  jours humides communs aux deux sources : {both_wet:.0%} des jours humides de l'une ou l'autre")

def swe(pr, ts, ddf):
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
O = per_winter(obs); cal = np.isfinite(O[CAL]).sum(0) >= 15; val = np.isfinite(O[VAL]).sum(0) >= 10
def score(M, rows, sel):
    ok = np.isfinite(O[rows][:, sel]); mo, mm = np.nanmean(O[rows][:, sel], 0), np.nanmean(np.where(ok, M[rows][:, sel], np.nan), 0)
    return np.mean(np.abs(mm - mo)), np.mean(mm - mo), np.corrcoef(mm, mo)[0, 1], mo.mean(), mm.mean()
def yearly(M, rows, sel):
    out = []
    for j in sel.nonzero()[0]:
        ok = np.isfinite(O[rows, j])
        if ok.sum() >= 10 and np.nanmean(O[rows, j]) >= 5: out.append(np.corrcoef(O[rows, j][ok], M[rows, j][ok])[0, 1])
    return np.median(out) if out else float("nan")
def daily(flag, sel):
    rows = (season & (winter > 2000))[:, None] & valid[:, sel]
    hit = (flag[:, sel] & obs[:, sel] & rows).sum(); miss = (~flag[:, sel] & obs[:, sel] & rows).sum(); false = (flag[:, sel] & ~obs[:, sel] & rows).sum()
    return hit / (hit + miss), false / (hit + false)
bands = (("< 300 m", alt < 300), ("300-800 m", (alt >= 300) & (alt < 800)), ("800-1500 m", (alt >= 800) & (alt < 1500)), (">= 1500 m", alt >= 1500))
best = {}
for name, pr in (("ERA5", era), ("E-OBS", rr)):
    res = []
    for ts, ddf, s0 in itertools.product((0.5, 1.0, 1.5, 2.0), (1.0, 1.5, 2.0, 3.0, 4.0, 5.0), (1.0, 2.0, 5.0)):
        M = per_winter(swe(pr, ts, ddf) >= s0); res.append((score(M, CAL, cal), score(M, VAL, val), ts, ddf, s0))
    res.sort(key=lambda x: x[0][0]); c, v, ts, ddf, s0 = res[0]; best[name] = (ts, ddf, s0)
    print(f"\nPluie {name} : {cal.sum()} stations au calage, {val.sum()} au contrôle")
    print("  trois meilleurs réglages (Ts, fonte, seuil) sur 1971-2000, et leur contrôle sur 2001-2020 :")
    for c, v, a, b, d in res[:3]: print(f"    {a:3.1f} °C, {b:3.1f} mm, {d:.0f} mm : calage erreur {c[0]:4.1f} biais {c[1]:+5.1f} | contrôle erreur {v[0]:4.1f} biais {v[1]:+5.1f} corr. {v[2]:.3f}")
    flag = swe(pr, ts, ddf) >= s0; M = per_winter(flag)
    for label, sel in bands:
        k = sel & val
        if not k.any(): continue
        e, b, rc, mo, mm = score(M, VAL, k); h, f = daily(flag, k)
        print(f"    {label:11s} {k.sum():4d} st. : observé {mo:5.1f}, calculé {mm:5.1f}, erreur {e:4.1f}, biais {b:+5.1f}, corr. entre hivers {yearly(M, VAL, k):.2f}, jours retrouvés {h:.0%}, fausses alertes {f:.0%}")
    k = cal & val; Mm = np.where(np.isfinite(O), M, np.nan)
    print(f"    changement 2001-2020 moins 1971-2000 ({k.sum()} st.) : observé {np.nanmean(O[VAL][:, k]) - np.nanmean(O[CAL][:, k]):+.1f}, calculé {np.nanmean(Mm[VAL][:, k]) - np.nanmean(Mm[CAL][:, k]):+.1f} jours")
np.save(sys.argv[4], np.array([best["ERA5"], best["E-OBS"]]))
