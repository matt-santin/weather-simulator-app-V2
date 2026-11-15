"""Jours de neige au sol par hiver en quelques lieux : données passées et modèle corrigé sur 1971-2000
et 1991-2020, puis 2031-2060 et 2071-2100 ; et d'où vient l'écart (jours froids, jours froids et humides).

    PYTHONPATH=. python figures/neige/lieux.py
"""
from datetime import date
import numpy as np
from src.app.store import Store
s = Store(); TS, DDF, S0 = 0.5, 4.0, 2.0
places = [("Lyon", 45.75, 4.85), ("Strasbourg", 48.58, 7.75), ("Besançon", 47.24, 6.02), ("Grenoble", 45.19, 5.72), ("Munich", 48.14, 11.58),
          ("Pontarlier", 46.90, 6.35), ("Le Puy-en-Velay", 45.04, 3.88), ("Oslo", 59.91, 10.75), ("Varsovie", 52.23, 21.01), ("Berlin", 52.52, 13.40)]
def run(source, cell, y0, y1):
    """Jours de neige au sol (nov.-avril), température moyenne et pluie de déc.-fév., par hiver."""
    a, b = date(y0 - 1, 8, 1), date(y1, 7, 31)
    v = s.values(source, cell, a, b, ("tas", "pr")); tas, pr = v["tas"], v["pr"]
    d = np.arange(np.datetime64(a.isoformat()), np.datetime64(b.isoformat()) + np.timedelta64(1, "D"))
    month = d.astype("datetime64[M]").astype(int) % 12 + 1; day1 = (month == 8) & (d.astype("datetime64[M]").astype("datetime64[D]") == d)
    swe = 0.0; flag = np.zeros(tas.size, bool)
    for k in range(tas.size):
        if day1[k]: swe = 0.0
        swe = max(swe + (pr[k] if tas[k] < TS else 0.0) - DDF * max(tas[k], 0.0), 0.0); flag[k] = swe >= S0
    n = y1 - y0 + 1; djf = np.isin(month, (12, 1, 2)); cold = np.isin(month, (11, 12, 1, 2, 3, 4))
    return flag[cold].sum() / n, tas[djf].mean(), pr[djf].sum() / n, (tas[cold] < TS).mean() * 181, ((tas[cold] < TS) & (pr[cold] >= 1)).sum() / n
print(f"{'lieu':16s} | 1971-2000 : passé modèle | 1991-2020 : passé modèle | 2031-60 2071-2100 | rapport au modèle 71-00")
rows = []
for name, lat, lon in places:
    c = s.cell(lat, lon)
    r = {k: run(src, c, y0, y1) for k, (src, y0, y1) in dict(p7=("era5", 1971, 2000), m7=("cordex", 1971, 2000), p9=("era5", 1991, 2020), m9=("cordex", 1991, 2020), f1=("cordex", 2031, 2060), f2=("cordex", 2071, 2100)).items()}
    rows.append((name, r))
    print(f"{name:16s} |            {r['p7'][0]:5.1f} {r['m7'][0]:6.1f} |            {r['p9'][0]:5.1f} {r['m9'][0]:6.1f} | {r['f1'][0]:7.1f} {r['f2'][0]:9.1f} | {r['f1'][0]/r['m7'][0]:5.0%} {r['f2'][0]/r['m7'][0]:5.0%}")
print("\nD'où vient l'écart modèle / passé : hiver (déc.-fév.) température moyenne (°C), jours froids (tas < 0,5 °C, nov.-avril), jours froids et humides (>= 1 mm)")
for name, r in rows:
    print(f"{name:16s} 71-00 : T {r['p7'][1]:5.2f} / {r['m7'][1]:5.2f}, froids {r['p7'][3]:5.1f} / {r['m7'][3]:5.1f}, froids humides {r['p7'][4]:4.1f} / {r['m7'][4]:4.1f}"
          f" || 91-20 : T {r['p9'][1]:5.2f} / {r['m9'][1]:5.2f}, froids {r['p9'][3]:5.1f} / {r['m9'][3]:5.1f}, froids humides {r['p9'][4]:4.1f} / {r['m9'][4]:4.1f}")
