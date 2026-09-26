"""Fields rebuilt from corrected ones, after src.correction.qdm.

    python -m src.correction.derive tn_tx    days with tasmin > tasmax swapped, in place
    python -m src.correction.derive huss     from corrected hurs, tas and ps
    python -m src.correction.derive rsus     corrected rsds x corrected albedo

Run from the repo root, with the external drive plugged in, once the fields
they need are corrected.

- tn_tx: tasmax and tasmin are corrected apart, so a few days may end with
  tasmin > tasmax; the two values are swapped there. Running it again changes
  nothing.
- huss: from hurs, tas and ps, as ERA5 huss is built from d2m and sp, with the
  IFS saturation vapour pressure over water. The CORDEX fields are daily
  means where ERA5 derives huss hour by hour: a small gap is expected.
- rsus: the albedo rsus / rsds is corrected (variable alb), and rsus is
  rebuilt from it, so that it never exceeds rsds.
"""

import logging
import sys

import numpy as np
import xarray as xr

from src.correction.qdm import OUT, YEARS
from src.correction.remap import target as remapped
from src.download.era5 import saturation

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("derive")


def corrected(name: str, year: int) -> xr.DataArray:
    return xr.open_dataarray(OUT / remapped(name, year).name).load()


def write(da: xr.DataArray, year: int) -> None:
    path = OUT / remapped(da.name, year).name
    part = path.with_suffix(".part")
    da.to_netcdf(part, encoding={da.name: {"zlib": True, "complevel": 4}})
    part.rename(path)


def tn_tx(year: int) -> int:
    tx, tn = corrected("tasmax", year), corrected("tasmin", year)
    swap = (tn > tx).values
    if swap.any():
        hi, lo = np.where(swap, tn, tx), np.where(swap, tx, tn)
        write(tx.copy(data=hi), year)
        write(tn.copy(data=lo), year)
    return int(swap.sum())


def huss(year: int) -> None:
    hurs, tas, ps = corrected("hurs", year), corrected("tas", year), corrected("ps", year)
    e = hurs.values / 100 * saturation(tas.values)
    da = hurs.copy(data=(0.622 * e / (ps.values - 0.378 * e)).astype("float32")).rename("huss")
    da.attrs = {"standard_name": "specific_humidity", "long_name": "Near-Surface Specific Humidity",
                "units": "1", "bias_correction": "rebuilt from QDM-corrected hurs, tas and ps"}
    write(da, year)


def rsus(year: int) -> None:
    rsds, alb = corrected("rsds", year), corrected("alb", year)
    da = rsds.copy(data=(rsds.values * alb.values).astype("float32")).rename("rsus")
    da.attrs = {"standard_name": "surface_upwelling_shortwave_flux_in_air",
                "long_name": "Surface Upwelling Shortwave Radiation", "units": "W m-2",
                "bias_correction": "QDM-corrected rsds times QDM-corrected albedo rsus / rsds"}
    write(da, year)


def main(argv: list[str]) -> int:
    steps = {"tn_tx": tn_tx, "huss": huss, "rsus": rsus}
    if len(argv) != 1 or argv[0] not in steps:
        print(__doc__)
        return 1
    step = argv[0]
    total = 0
    for y in YEARS:
        n = steps[step](y)
        if step == "tn_tx":
            total += n
            if n:
                log.info("%d : %d valeurs echangees", y, n)
    if step == "tn_tx":
        log.info("tasmin > tasmax : %d valeurs echangees en tout", total)
    log.info("%s fait, %d annees", step, len(YEARS))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
