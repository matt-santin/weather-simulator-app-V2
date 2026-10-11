"""Maximum annuel de Tx à Paris et Lyon, ERA5-Land 1970-2025 et CORDEX corrigé 1970-2100 (maille 0,1°).

    python figures/climat/txx_paris_lyon.py                  # la simulation servie (cordex010)
    python figures/climat/txx_paris_lyon.py cordex010_rca4   # un autre groupe du stockage

Le modèle est lu dans le stockage (attribut simulation) ; figure et valeurs :
figures/climat/txx_paris_lyon_<modèle>.png et .csv.
"""
import sys
import warnings

import matplotlib.pyplot as plt
import pandas as pd
import xarray as xr

warnings.filterwarnings("ignore")
Z = "data/serve/point.zarr"
LIEUX = {"Paris": (48.86, 2.35), "Lyon": (45.76, 4.84)}
TAG = {"RCA4": "RCA4", "ICON-CLM": "MPI"}  # modèle régional : suffixe des fichiers

groupe = sys.argv[1] if len(sys.argv) > 1 else "cordex010"
sim = xr.open_zarr(Z, group=groupe, consolidated=False).tasmax.attrs["simulation"]
tag = TAG[sim["regional"]]
SOURCES = [("era5land", "ERA5-Land", "#2a78d6"),
           (groupe, f"CORDEX corrigé ({sim['driving']} / {sim['regional']}, {sim['scenario']})", "#eb6834")]

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
table = {}
for ax, (lieu, (la, lo)) in zip(axes, LIEUX.items()):
    for g, nom, coul in SOURCES:
        tx = xr.open_zarr(Z, group=g, consolidated=False).tasmax
        txx = tx.sel(latitude=la, longitude=lo, method="nearest").groupby("time.year").max().load()
        table[(lieu, "ERA5-Land" if g == "era5land" else tag)] = txx.to_series()
        ax.plot(txx.year, txx, color=coul, lw=1, alpha=0.45)
        ax.plot(txx.year, txx.rolling(year=20, center=True).mean(), color=coul, lw=2.2, label=f"{nom} : valeur annuelle (trait fin), moyenne glissante 20 ans (épais)")
        i = int(txx.argmax())
        ax.annotate(f"{float(txx[i]):.1f}", (int(txx.year[i]), float(txx[i])), textcoords="offset points",
                    xytext=(0, 5), ha="center", fontsize=8, color="#52514e")
    ax.set_title(lieu, loc="left", fontsize=12)
    ax.grid(axis="y", color="#e5e4e0", lw=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(1968, 2102)
axes[0].set_ylabel("Tx maximal de l'année (°C)")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0.06, 0))
fig.suptitle("Température maximale de l'année, maille 0,1°", x=0.06, ha="left", fontsize=13)
fig.tight_layout(rect=(0, 0.1, 1, 1))
fig.savefig(f"figures/climat/txx_paris_lyon_{tag}.png", dpi=150)
csv = pd.DataFrame(table).round(1)
csv.columns = [f"{lieu} {source}" for lieu, source in csv.columns]
csv.index.name = "annee"
csv.to_csv(f"figures/climat/txx_paris_lyon_{tag}.csv")
