"""Maximum annuel de Tx à Paris et Lyon, ERA5-Land 1970-2025 et CORDEX corrigé 1970-2100 (maille 0,1°)."""
import warnings
import matplotlib.pyplot as plt
import xarray as xr

warnings.filterwarnings("ignore")
Z = "data/serve/point.zarr"
LIEUX = {"Paris": (48.86, 2.35), "Lyon": (45.76, 4.84)}
SOURCES = [("era5land", "ERA5-Land", "#2a78d6"), ("cordex010", "CORDEX corrigé (RCP4.5)", "#eb6834")]

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
for ax, (lieu, (la, lo)) in zip(axes, LIEUX.items()):
    for groupe, nom, coul in SOURCES:
        tx = xr.open_zarr(Z, group=groupe, consolidated=False).tasmax
        txx = tx.sel(latitude=la, longitude=lo, method="nearest").groupby("time.year").max().load()
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
axes[0].legend(frameon=False, fontsize=8, loc="upper left")
fig.suptitle("Température maximale de l'année, maille 0,1°", x=0.06, ha="left", fontsize=13)
fig.tight_layout()
fig.savefig("figures/climat/txx_paris_lyon.png", dpi=150)
