"""Températures et précipitations servies par le site (données passées) à un échantillon de stations,
de juillet 1970 à juin 2020 : 1 500 stations tirées au hasard, plus celles de France, Suisse,
Autriche et Italie.

    PYTHONPATH=. python figures/neige/lire.py data/neige/stations.npz data/neige/meteo.npz          (20 s)
"""
import sys, time
from datetime import date
import numpy as np
from src.app.store import Store
st = np.load(sys.argv[1]); s = Store()
rng = np.random.default_rng(0)
order = rng.permutation(st["ids"].size)
pick, cells = [], []
for k in order:
    c = s.cell(float(st["lat"][k]), float(st["lon"][k]))
    if c is None or c.fine is None: continue
    keep = st["cn"][k] in ("FR", "CH", "AT", "IT") or len(pick) < 1500
    if keep: pick.append(k); cells.append(c)
    if len(pick) >= 2600: break
pick = np.array(pick); print(len(pick), "stations lues")
a, b = date(1970, 7, 1), date(2020, 6, 30); t = time.time()
tas = np.empty((len(pick), (b - a).days + 1), "float32"); pr = np.empty_like(tas); tn = np.empty_like(tas); tx = np.empty_like(tas)
for i, c in enumerate(cells):
    v = s.values("era5", c, a, b, ("tas", "tasmin", "tasmax", "pr"))
    tas[i], tn[i], tx[i], pr[i] = v["tas"], v["tasmin"], v["tasmax"], v["pr"]
print(f"{time.time()-t:.0f} s")
np.savez_compressed(sys.argv[2], pick=pick, tas=tas, tn=tn, tx=tx, pr=pr)
