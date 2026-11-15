"""Hauteurs de neige ECA&D (data/stations/ecad/blend/ECA_blend_sd.zip) : une série journalière par
station, de juillet 1970 à juin 2020, pour les stations qui ont au moins la moitié des jours.

    python figures/neige/stations.py data/neige/stations.npz          (90 s)
"""
import sys, zipfile, io, time
import numpy as np
z = zipfile.ZipFile("data/stations/ecad/blend/ECA_blend_sd.zip")
def dms(s):
    sign = -1 if s.strip().startswith("-") else 1
    d, m, sec = s.strip().lstrip("+-").split(":"); return sign * (int(d) + int(m) / 60 + int(sec) / 3600)
meta = {}
for line in z.read("stations.txt").decode("latin-1").splitlines():
    p = line.split(",")
    if len(p) >= 6 and p[0].strip().isdigit():
        meta[int(p[0])] = (p[1].strip(), p[2].strip(), dms(p[3]), dms(p[4]), int(p[5]))
T0 = np.datetime64("1970-07-01"); N = (np.datetime64("2020-07-01") - T0).astype(int)   # 50 hivers 1970-71 .. 2019-20
out = {}; t = time.time()
for name in z.namelist():
    if not name.startswith("SD_STAID"): continue
    sid = int(name[8:14])
    if sid not in meta: continue
    raw = z.read(name).decode("latin-1")
    k = raw.find("STAID,")
    if k < 0: continue
    body = raw[raw.find("\n", k) + 1:]
    try:
        a = np.loadtxt(io.StringIO(body), delimiter=",", usecols=(2, 3, 4), dtype=np.int64, ndmin=2)
    except Exception: continue
    if a.size == 0 or a[-1, 0] < 19710101 or a[0, 0] > 20200101: continue
    d = a[:, 0]; dates = (d // 10000 - 1970).astype("datetime64[Y]").astype("datetime64[M]") + (d // 100 % 100 - 1)
    dates = dates.astype("datetime64[D]") + (d % 100 - 1)
    idx = (dates - T0).astype(int); ok = (idx >= 0) & (idx < N) & (a[:, 2] == 0) & (a[:, 1] >= 0)
    sd = np.full(N, -1, np.int16); sd[idx[ok]] = np.minimum(a[ok, 1], 30000)
    if (sd >= 0).sum() < 0.5 * N: continue
    out[sid] = sd
print(len(out), "stations avec au moins la moitié des jours de juillet 1970 à juin 2020,", f"{time.time()-t:.0f} s")
ids = np.array(sorted(out))
np.savez_compressed(sys.argv[1], ids=ids, sd=np.stack([out[i] for i in ids]),
                    lat=np.array([meta[i][2] for i in ids]), lon=np.array([meta[i][3] for i in ids]),
                    alt=np.array([meta[i][4] for i in ids]), name=np.array([meta[i][0] for i in ids]),
                    cn=np.array([meta[i][1] for i in ids]))
