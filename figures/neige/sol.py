"""Le sol chaud : erreur par mois, puis variante avec une fonte par le sol (moyenne de l'air sur les N jours passés).

    python figures/neige/sol.py data/neige/stations.npz data/neige/meteo.npz
"""
import sys, itertools
import numpy as np
st = np.load(sys.argv[1]); m = np.load(sys.argv[2]); p = m["pick"]
sd = st["sd"][p].T; tas = m["tas"].T; pr = m["pr"].T; alt = st["alt"][p]
days = np.arange("1970-07-01", "2020-07-01", dtype="datetime64[D]")
month = days.astype("datetime64[M]").astype(int) % 12 + 1
first = days.astype("datetime64[M]").astype("datetime64[D]") == days
winter = (days.astype("datetime64[Y]").astype(int) + 1970) + (month >= 7)
season = np.isin(month, (11, 12, 1, 2, 3, 4)); W = np.arange(1971, 2021); CAL, VAL = W <= 2000, W > 2000
valid = sd >= 0; obs = sd >= 1

def soil(n):
    """Moyenne de la température de l'air sur les n jours précédents (le jour même exclu)."""
    c = np.cumsum(np.vstack([np.zeros((1, tas.shape[1]), "float64"), tas]), axis=0)
    out = np.empty(tas.shape, "float32")
    for k in range(tas.shape[0]):
        a = max(k - n, 0); out[k] = (c[k] - c[a]) / max(k - a, 1) if k > 0 else tas[0]
    return out
def swe(ts, ddf, g=0.0, ground=None):
    s = np.zeros(tas.shape[1], "float32"); out = np.empty(tas.shape, "float32")
    fall = np.where(tas < ts, pr, 0.0); melt = ddf * np.maximum(tas, 0.0)
    if g: melt = melt + g * np.maximum(ground, 0.0)
    for k in range(tas.shape[0]):
        if first[k] and month[k] == 8: s[:] = 0
        s = np.maximum(s + fall[k] - melt[k], 0.0); out[k] = s
    return out
def per_winter(flag, months=(11, 12, 1, 2, 3, 4)):
    sel = np.isin(month, months); out = np.full((W.size, sd.shape[1]), np.nan)
    for i, w in enumerate(W):
        rows = sel & (winter == w); n = valid[rows].sum(0); full = n >= 0.95 * rows.sum()
        out[i, full] = (flag[rows] & valid[rows]).sum(0)[full] * rows.sum() / n[full]
    return out
O = per_winter(obs); cal = np.isfinite(O[CAL]).sum(0) >= 15; val = np.isfinite(O[VAL]).sum(0) >= 10
def score(M, Oref, rows, sel):
    ok = np.isfinite(Oref[rows][:, sel]); mo, mm = np.nanmean(Oref[rows][:, sel], 0), np.nanmean(np.where(ok, M[rows][:, sel], np.nan), 0)
    return np.nanmean(np.abs(mm - mo)), np.nanmean(mm - mo), np.nanmean(mo), np.nanmean(mm)
low, mid = alt < 300, (alt >= 300) & (alt < 800)
base = swe(0.5, 4.0) >= 2.0
print("1. Calcul actuel (0,5 °C, 4 mm, 2 mm), contrôle 2001-2020 : jours de neige au sol par mois, observé / calculé (biais)")
print(f"   {'mois':10s} {'moins de 300 m':>26s} {'300 à 800 m':>26s}")
for mo_, name in ((11, "novembre"), (12, "décembre"), (1, "janvier"), (2, "février"), (3, "mars"), (4, "avril")):
    Om, Mm = per_winter(obs, (mo_,)), per_winter(base, (mo_,)); line = f"   {name:10s}"
    for sel in (low & val, mid & val):
        e, b, o, c = score(Mm, Om, VAL, sel); line += f" {o:8.1f} / {c:5.1f} ({b:+5.1f})    "
    print(line)
# première neige de la saison : tient-elle aussi longtemps que calculé ?
print("\n2. Variante avec fonte par le sol : fonte = DDF x air + G x moyenne de l'air des N jours passés (parts positives)")
res = []
grounds = {n: soil(n) for n in (10, 20, 30)}
for n, g, ddf, s0 in itertools.product((10, 20, 30), (0.5, 1.0, 2.0), (2.0, 3.0, 4.0), (1.0, 2.0)):
    M = per_winter(swe(0.5, ddf, g, grounds[n]) >= s0)
    res.append((score(M, O, CAL, cal)[0], n, g, ddf, s0, M))
res.sort(key=lambda r: r[0])
M0 = per_winter(base)
print(f"   sans sol                         : calage {score(M0, O, CAL, cal)[0]:.2f}, contrôle {score(M0, O, VAL, val)[0]:.2f} (biais {score(M0, O, VAL, val)[1]:+.1f}) ; < 300 m {score(M0, O, VAL, low & val)[0]:.2f} ; 300-800 m {score(M0, O, VAL, mid & val)[0]:.2f}")
for e, n, g, ddf, s0, M in res[:3]:
    print(f"   N={n:2d} j, G={g:3.1f}, DDF={ddf:3.1f}, seuil {s0:.0f} mm : calage {e:.2f}, contrôle {score(M, O, VAL, val)[0]:.2f} (biais {score(M, O, VAL, val)[1]:+.1f}) ; < 300 m {score(M, O, VAL, low & val)[0]:.2f} ; 300-800 m {score(M, O, VAL, mid & val)[0]:.2f}")
e, n, g, ddf, s0, M = res[0]; flag = swe(0.5, ddf, g, grounds[n]) >= s0
print("\n3. Avec le meilleur terme de sol, par mois (moins de 300 m, contrôle) : observé / calculé (biais)")
for mo_, name in ((11, "novembre"), (12, "décembre"), (1, "janvier"), (2, "février"), (3, "mars"), (4, "avril")):
    Om, Mm = per_winter(obs, (mo_,)), per_winter(flag, (mo_,)); e_, b, o, c = score(Mm, Om, VAL, low & val)
    print(f"   {name:10s} {o:5.1f} / {c:5.1f} ({b:+5.1f})")
def daily(f, sel):
    rows = (season & (winter > 2000))[:, None] & valid[:, sel]
    hit = (f[:, sel] & obs[:, sel] & rows).sum(); miss = (~f[:, sel] & obs[:, sel] & rows).sum(); false = (f[:, sel] & ~obs[:, sel] & rows).sum()
    return hit / (hit + miss), false / (hit + false)
print("\n4. Jour par jour, moins de 300 m, contrôle : jours de neige retrouvés, fausses alertes")
print("   sans sol : %.0f %%, %.0f %%" % tuple(100 * x for x in daily(base, low & val)), "| avec sol : %.0f %%, %.0f %%" % tuple(100 * x for x in daily(flag, low & val)))
