"""The CORDEX runs the correction chain can work on, chosen by WSA_MODEL.

    WSA_MODEL=mpi python -m src.correction.remap tas 1970-2100

    rca4  EC-EARTH r12i1p1 / SMHI-RCA4, EUR-11, historical then rcp45 (default:
          the run the site serves)
    mpi   MPI-ESM1-2-HR r1i1p1f1 / ICON-CLM-202407-1-1 (CLMcom-DWD), EUR-12,
          historical then ssp370 (docs/choix_modele_cmip6.md)

Both runs share the same rotated grid (412 x 424 cells, pole 39.25 N, 162 W;
coordinates equal to 4e-15 deg), so the remapping weights onto ERA5 and
ERA5-Land are computed once and serve both.

Each run writes to its own folders: remapped and corrected files on the drive
(cordex/<out>_025, <out>_025_qdm, <out>_010, <out>_010_qdm), tables and logs
under data/correction/<tables>. The files of the derived chain are always one
per year, named after the run.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from src.config import ARCHIVE


@dataclass(frozen=True)
class Model:
    key: str
    domain: str  # as in the file names
    src: Path  # downloaded daily files
    stem: str  # file name between the domain and the time step, {exp} for the experiment
    hist_end: int  # last year of the historical experiment
    scenario: str
    out: str  # prefix of the remapped and corrected folders on the drive
    tables: str  # sub-folder of data/correction, "" for the first run

    def yearly(self, name: str, year: int) -> str:
        exp = "historical" if year <= self.hist_end else self.scenario
        return (f"{name}_{self.domain}_{self.stem.format(exp=exp)}_day_"
                f"{year}0101-{year}1231.nc")

    def source(self, name: str, year: int) -> Path:
        """The downloaded file that holds that year: one per year from the CDS,
        several per file from ESGF."""
        path = self.src / self.yearly(name, year)
        if path.exists():
            return path
        stem = self.yearly(name, year).rsplit("_", 1)[0]
        for p in self.src.glob(stem + "_*.nc"):
            start, end = p.stem.rsplit("_", 1)[1].split("-")
            if int(start[:4]) <= year <= int(end[:4]):
                return p
        raise FileNotFoundError(f"{name} {year} absent de {self.src}")


MODELS = {
    "rca4": Model("rca4", "EUR-11", ARCHIVE / "cordex" / "eur11",
                  "ICHEC-EC-EARTH_{exp}_r12i1p1_SMHI-RCA4_v1", 2005, "rcp45", "eur11", ""),
    "mpi": Model("mpi", "EUR-12", ARCHIVE / "cordex" / "eur12_mpi-esm1-2-hr_icon-clm",
                 "MPI-ESM1-2-HR_{exp}_r1i1p1f1_CLMcom-DWD_ICON-CLM-202407-1-1_v1-r1",
                 2014, "ssp370", "eur12_mpi", "mpi"),
}

MODEL = MODELS[os.environ.get("WSA_MODEL", "rca4")]
