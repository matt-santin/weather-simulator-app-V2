"""Épaisseur du manteau neigeux : le stock du degré-jour converti en centimètres, contre les hauteurs
de neige ECA&D.

    PYTHONPATH=. python figures/neige/epaisseur.py            (2 min, sans le LaCie)

Même stock que le site (0,5 °C, 4 mm, 2 mm), tas ramené à l'altitude de la station par le gradient du
mois (src.app.domain.altitude), comme le site le fait pour un lieu dont il connaît l'altitude.
Deux conversions en épaisseur :
  - densité fixe : épaisseur (cm) = stock (mm) x 100 / densité (kg/m3) ;
  - densité qui croît avec l'âge : la neige tombe à RHO_F, le manteau se tasse vers RHO_MAX avec une
    constante de temps TAU (jours) ; la fonte retire de l'épaisseur en proportion du stock.
Calage sur les hivers 1971-2000, contrôle sur 2001-2020. Grandeurs par hiver (nov.-avril) : épaisseur
maximale, jours à SEUIL cm ou plus.
Puis, en 150 stations enneigées : modèle corrigé contre données passées sur 1991-2020.
"""
from datetime import date

import numpy as np

from src.app.domain import altitude
from src.app.store import Store
from src.config import ROOT

SEUIL = 20.0
st = np.load(ROOT / "data" / "neige" / "stations.npz")
m = np.load(ROOT / "data" / "neige" / "meteo.npz")
p = m["pick"]
sd = st["sd"][p].T.astype("float32")
tas0, pr = m["tas"].T, m["pr"].T
alt, name, lat, lon = st["alt"][p].astype(float), st["name"][p].astype(str), st["lat"][p], st["lon"][p]
s = Store()
cells = [s.cell(float(a), float(b)) for a, b in zip(lat, lon)]
zc = np.array([s.elevation(c) if s.corrects(c) else np.nan for c in cells], float)
dz = np.where(np.isfinite(zc), zc - alt, 0.0)
days = np.arange("1970-07-01", "2020-07-01", dtype="datetime64[D]")
month = days.astype("datetime64[M]").astype(int) % 12 + 1
first = days.astype("datetime64[M]").astype("datetime64[D]") == days
winter = (days.astype("datetime64[Y]").astype(int) + 1970) + (month >= 7)
season = np.isin(month, (11, 12, 1, 2, 3, 4))
W = np.arange(1971, 2021)
CAL, VAL = W <= 2000, W > 2000
G = np.asarray(altitude.LAPSE_K_PER_KM["tas"])
tas = tas0 + G[month - 1][:, None] * dz[None, :] / 1000.0
valid = sd >= 0


def pack(tas, pr, month, first, rho_f=None, rho_max=None, tau=None, ts=0.5, ddf=4.0):
    """Stock (mm) et, si rho_f est donné, épaisseur (cm) avec tassement."""
    n = tas.shape[1]
    swe = np.zeros(n, "float32")
    depth = np.zeros(n, "float32")
    S = np.empty(tas.shape, "float32")
    D = np.empty(tas.shape, "float32") if rho_f else None
    t = np.nan_to_num(tas, nan=10.0)
    fall = np.where(t < ts, np.nan_to_num(pr), 0.0).astype("float32")
    melt = (ddf * np.maximum(t, 0.0)).astype("float32")
    for k in range(tas.shape[0]):
        if first[k] and month[k] == 8:
            swe[:] = 0
            depth[:] = 0
        before = swe + fall[k]
        swe = np.maximum(before - melt[k], 0.0)
        if rho_f:
            depth = depth + fall[k] * 100.0 / rho_f
            depth = np.where(before > 0, depth * swe / np.maximum(before, 1e-6), 0.0)
            rho = np.where(depth > 0, swe * 100.0 / np.maximum(depth, 1e-6), rho_f)
            rho = np.minimum(rho + (rho_max - rho) / tau, rho_max)
            depth = (swe * 100.0 / rho).astype("float32")
            D[k] = depth
        S[k] = swe
    return S, D


def per_winter(x, fn):
    """fn sur les jours valides de chaque hiver (nov.-avril), NaN sous 95 % de jours valides."""
    out = np.full((W.size, x.shape[1]), np.nan)
    for i, w in enumerate(W):
        rows = season & (winter == w)
        v = valid[rows]
        full = v.sum(0) >= 0.95 * rows.sum()
        out[i, full] = fn(np.where(v, x[rows], np.nan))[full]
    return out


mx = lambda a: np.nanmax(np.where(np.isfinite(a), a, -1), 0)
over = lambda a: (np.nan_to_num(a, nan=-1) >= SEUIL).sum(0).astype(float)
Omax, Oday = per_winter(sd, mx), per_winter(sd, over)
ok = lambda sel: (np.isfinite(Omax[sel]).sum(0) >= 10)


def score(Cmax, Cday, sel, mask):
    """Sur les hivers de sel et les stations de mask : moyennes observée et calculée du maximum,
    erreur absolue moyenne entre stations, idem pour les jours au-dessus du seuil ; corrélation médiane
    entre hivers du maximum."""
    have = np.isfinite(Omax[sel][:, mask])
    o = np.nanmean(Omax[sel][:, mask], 0)
    c = np.nanmean(np.where(have, Cmax[sel][:, mask], np.nan), 0)
    od = np.nanmean(Oday[sel][:, mask], 0)
    cd = np.nanmean(np.where(have, Cday[sel][:, mask], np.nan), 0)
    r = [np.corrcoef(Omax[sel][have[:, j], k], Cmax[sel][have[:, j], k])[0, 1]
         for j, k in enumerate(np.nonzero(mask)[0]) if np.nanstd(Omax[sel][have[:, j], k]) > 0]
    return o.mean(), c.mean(), np.abs(c - o).mean(), od.mean(), cd.mean(), np.abs(cd - od).mean(), np.nanmedian(r)


S, _ = pack(tas, pr, month, first)
snowy_cal = ok(CAL) & (np.nanmean(Omax[CAL], 0) >= 10)
snowy_val = ok(VAL) & (np.nanmean(Omax[VAL], 0) >= 10)
print(f"{sd.shape[1]} stations ; maximum d'hiver moyen d'au moins 10 cm : calage {snowy_cal.sum()}, contrôle {snowy_val.sum()}")

runs = {}
for rho in (100, 150, 200, 250, 300):
    Dp = S * 100.0 / rho
    runs[f"fixe {rho}"] = (per_winter(Dp, mx), per_winter(Dp, over))
for rf in (80, 100, 150):
    for rm in (250, 300, 350, 400):
        for tau in (10, 20, 40):
            _, Dp = pack(tas, pr, month, first, rf, rm, tau)
            runs[f"tassement {rf}/{rm}/{tau}"] = (per_winter(Dp, mx), per_winter(Dp, over))
rank = sorted(runs, key=lambda k: score(*runs[k], CAL, snowy_cal)[2] / 10 + score(*runs[k], CAL, snowy_cal)[5] / 20)
print("\nCalage 1971-2000 (stations à 10 cm ou plus de maximum moyen) ; classement par erreur sur le maximum et sur les jours")
print(f"  {'réglage':22s} | maximum d'hiver (cm) : obs. calc. erreur | jours >= {SEUIL:.0f} cm : obs. calc. erreur | corr.")
show = rank[:5] + [k for k in runs if k.startswith("fixe")]
for k in dict.fromkeys(show):
    a = score(*runs[k], CAL, snowy_cal)
    b = score(*runs[k], VAL, snowy_val)
    print(f"  {k:22s} | cal {a[0]:5.1f} {a[1]:5.1f} {a[2]:5.1f} | {a[3]:5.1f} {a[4]:5.1f} {a[5]:5.1f} | {a[6]:.2f} || contrôle {b[0]:5.1f} {b[1]:5.1f} {b[2]:5.1f} | {b[3]:5.1f} {b[4]:5.1f} {b[5]:5.1f} | {b[6]:.2f}")

best = rank[0]
bfix = min((k for k in runs if k.startswith("fixe")), key=lambda k: score(*runs[k], CAL, snowy_cal)[2] / 10 + score(*runs[k], CAL, snowy_cal)[5] / 20)
print(f"\nRetenus : {best} ; densité fixe : {bfix}")
for label, key in (("tassement", best), ("densité fixe", bfix)):
    Cmax, Cday = runs[key]
    print(f"\nContrôle 2001-2020, {label} ({key}), par altitude de la station :")
    print(f"  {'':12s} {'st.':>4s} | maximum d'hiver (cm) : obs. calc. erreur | jours >= {SEUIL:.0f} cm : obs. calc. erreur | corr.")
    for lab, sel in (("< 300 m", alt < 300), ("300-800 m", (alt >= 300) & (alt < 800)), ("800-1500 m", (alt >= 800) & (alt < 1500)), (">= 1500 m", alt >= 1500), ("toutes", alt > -1000), ("max >= 20 cm", np.nanmean(Omax[VAL], 0) >= 20)):
        k = sel & ok(VAL)
        if k.sum() < 3:
            continue
        a = score(Cmax, Cday, VAL, k)
        print(f"  {lab:12s} {k.sum():4d} | {a[0]:5.1f} {a[1]:5.1f} {a[2]:5.1f} | {a[3]:5.1f} {a[4]:5.1f} {a[5]:5.1f} | {a[6]:.2f}")
    # Le seuil comme critère d'affichage : hiver par hiver, le seuil est-il franchi ?
    k = ok(VAL)
    o, c = Omax[VAL][:, k] >= SEUIL, Cmax[VAL][:, k] >= SEUIL
    have = np.isfinite(Omax[VAL][:, k])
    hit, miss, false = (o & c & have).sum(), (o & ~c & have).sum(), (~o & c & have).sum()
    print(f"  hivers où {SEUIL:.0f} cm sont atteints : observés {(o & have).sum()}, retrouvés {hit} ({hit / max((o & have).sum(), 1):.0%}), "
          f"manqués {miss}, annoncés à tort {false} ({false / max((c & have).sum(), 1):.0%} des annoncés)")
    rel = np.nanmean(np.where(have, Cmax[VAL][:, k], np.nan), 0) / np.nanmean(Omax[VAL][:, k], 0)
    big = np.nanmean(Omax[VAL][:, k], 0) >= 20
    print(f"  stations à 20 cm ou plus de maximum moyen ({big.sum()}) : rapport calculé / observé du maximum moyen, "
          f"quartiles {np.percentile(rel[big], 25):.2f} {np.percentile(rel[big], 50):.2f} {np.percentile(rel[big], 75):.2f}")

print("\nExemples, contrôle 2001-2020 : maximum d'hiver moyen observé / calculé (cm) ; jours >= seuil observés / calculés")
Cmax, Cday = runs[best]
for want in ("SAENTIS", "BROCKEN", "LIORAN", "CHAMONIX", "PONTARLIER", "OSLO", "MUENCHEN", "DAVOS", "FELDBERG/SCHW", "ZUGSPITZE", "FICHTELBERG", "OBERSTDORF", "KEMPTEN", "GARMISCH"):
    for j in np.nonzero(np.char.find(np.char.upper(name), want) >= 0)[0][:1]:
        if np.isfinite(Omax[VAL, j]).sum() >= 10:
            h = np.isfinite(Omax[VAL, j])
            print(f"  {name[j][:24]:24s} {alt[j]:5.0f} m | {np.nanmean(Omax[VAL, j]):6.1f} / {np.nanmean(Cmax[VAL, j][h]):6.1f} | {np.nanmean(Oday[VAL, j]):6.1f} / {np.nanmean(Cday[VAL, j][h]):6.1f}")

# Modèle corrigé contre données passées, 1991-2020, en 150 stations enneigées (au plus), à l'altitude de la station.
rf, rm, tau = (float(x) for x in best.split()[1].split("/")) if best.startswith("tassement") else (None, None, None)
pick = np.nonzero(ok(VAL) & (np.nanmean(Omax[VAL], 0) >= 20) & np.isfinite(zc))[0]
pick = np.random.default_rng(0).permutation(pick)[:150]
a, b = date(1990, 8, 1), date(2020, 7, 31)
d2 = np.arange("1990-08-01", "2020-08-01", dtype="datetime64[D]")
mo2 = d2.astype("datetime64[M]").astype(int) % 12 + 1
f2 = d2.astype("datetime64[M]").astype("datetime64[D]") == d2
w2 = (d2.astype("datetime64[Y]").astype(int) + 1970) + (mo2 >= 8)
se2 = np.isin(mo2, (11, 12, 1, 2, 3, 4))
res = {}
for src in ("era5", "cordex"):
    T = np.empty((d2.size, pick.size), "float32")
    P = np.empty_like(T)
    for i, j in enumerate(pick):
        v = s.values(src, s.cell(float(lat[j]), float(lon[j]), float(alt[j])), a, b, ("tas", "pr"))
        T[:, i], P[:, i] = v["tas"], v["pr"]
    Sx, Dx = pack(T, P, mo2, f2, rf, rm, tau)
    if Dx is None:
        Dx = Sx * 100.0 / float(bfix.split()[1])
    res[src] = (np.array([Dx[se2 & (w2 == y)].max(0) for y in range(1991, 2021)]).mean(0),
                np.array([(Dx[se2 & (w2 == y)] >= SEUIL).sum(0) for y in range(1991, 2021)]).mean(0),
                np.array([Dx[se2 & (w2 == y)].max(0) >= SEUIL for y in range(1991, 2021)]).mean(0))
print(f"\nModèle corrigé contre données passées, 1991-2020, {pick.size} stations à 20 cm ou plus de maximum moyen observé :")
for i, lab in enumerate(("maximum d'hiver moyen (cm)", f"jours >= {SEUIL:.0f} cm par hiver", f"part des hivers atteignant {SEUIL:.0f} cm")):
    e, c = res["era5"][i], res["cordex"][i]
    q = np.percentile(c / np.maximum(e, 1e-6), (25, 50, 75))
    print(f"  {lab:38s} passé {e.mean():6.2f}, modèle {c.mean():6.2f}, rapport modèle / passé par station : quartiles {q[0]:.2f} {q[1]:.2f} {q[2]:.2f}")
