"""The Köppen-Geiger class of a climate, from its twelve monthly means.

Criteria of Beck et al. 2023 (Sci. Data 10, 724, table 1 and methods; full
text read on Europe PMC, PMC10593765):

- the arid class B takes precedence over all others; its threshold is
  2 x MAT, plus 14, or plus 28 where more than 70 % of the precipitation falls
  in summer, plus nothing where more than 70 % falls in winter;
- temperate (C) and cold (D) are split at 0 degC on the coldest month, not
  Köppen's -3 degC;
- summer (winter) is the warmer (colder) of the two half-years April-September
  and October-March, whatever the hemisphere;
- s and w exclude each other: a summer is dry (s) only if more precipitation
  falls in winter, a winter dry (w) only in the opposite case.

One function for a single place (the climate diagram of the site, src.app.api.climate)
and for a whole grid (figures/climat/koppen_nous.py): columns are places.
"""

from __future__ import annotations

import numpy as np

# April-September and October-March, as month indices 0 to 11.
APR_SEP = [3, 4, 5, 6, 7, 8]
OCT_MAR = [9, 10, 11, 0, 1, 2]


def classify(temperature: np.ndarray, precipitation: np.ndarray) -> np.ndarray:
    """The class code ("Cfb", "BSk", ...) of each column, "" where a month is missing.

    temperature: (12, n) monthly mean air temperature, degC.
    precipitation: (12, n) precipitation of each month, mm.
    """
    T = np.asarray(temperature, dtype=float).reshape(12, -1)
    Pm = np.asarray(precipitation, dtype=float).reshape(12, -1)
    ok = np.isfinite(T).all(0) & np.isfinite(Pm).all(0)
    T = np.where(ok, T, 0.0)
    Pm = np.where(ok, Pm, 0.0)

    MAT, MAP = T.mean(0), Pm.sum(0)
    Tcold, Thot = T.min(0), T.max(0)
    Tmon10 = (T > 10).sum(0)
    Pdry = Pm.min(0)
    summer_first = T[APR_SEP].mean(0) > T[OCT_MAR].mean(0)
    Pa, Po = Pm[APR_SEP], Pm[OCT_MAR]
    Psummer = np.where(summer_first, Pa.sum(0), Po.sum(0))
    Pwinter = np.where(summer_first, Po.sum(0), Pa.sum(0))
    Psdry = np.where(summer_first, Pa.min(0), Po.min(0))
    Pswet = np.where(summer_first, Pa.max(0), Po.max(0))
    Pwdry = np.where(summer_first, Po.min(0), Pa.min(0))
    Pwwet = np.where(summer_first, Po.max(0), Pa.max(0))
    threshold = np.where(Pwinter > 0.7 * MAP, 2 * MAT,
                         np.where(Psummer > 0.7 * MAP, 2 * MAT + 28, 2 * MAT + 14))

    tropical = Tcold >= 18
    polar = Thot <= 10
    temperate = ~tropical & ~polar & (Tcold > 0)
    cold = ~tropical & ~polar & (Tcold <= 0)

    dry_summer = (Psdry < 40) & (Psdry < Pwwet / 3) & (Pwinter > Psummer)
    dry_winter = (Pwdry < Pswet / 10) & (Psummer >= Pwinter)
    second = np.where(dry_summer, "s", np.where(dry_winter, "w", "f"))
    third = np.where(Thot >= 22, "a", np.where(Tmon10 >= 4, "b", "c"))
    third_cold = np.where(Thot >= 22, "a", np.where(Tmon10 >= 4, "b", np.where(Tcold < -38, "d", "c")))

    code = np.full(T.shape[1], "", dtype="<U3")
    code[tropical] = np.where(Pdry >= 60, "Af", np.where(Pdry >= 100 - MAP / 25, "Am", "Aw"))[tropical]
    code[polar] = np.where(Thot > 0, "ET", "EF")[polar]
    code[temperate] = np.char.add(np.char.add("C", second), third)[temperate]
    code[cold] = np.char.add(np.char.add("D", second), third_cold)[cold]
    arid = MAP < 10 * threshold
    arid_code = np.char.add(np.where(MAP < 5 * threshold, "BW", "BS"), np.where(MAT >= 18, "h", "k"))
    code[arid] = arid_code[arid]
    code[~ok] = ""
    return code


def of_place(temperature: list[float | None], precipitation: list[float | None]) -> str | None:
    """The class of one place from its twelve months, or None if a month is missing."""
    if len(temperature) != 12 or len(precipitation) != 12:
        return None
    if any(v is None for v in (*temperature, *precipitation)):
        return None
    code = classify(np.array(temperature, dtype=float)[:, None], np.array(precipitation, dtype=float)[:, None])[0]
    return str(code) or None
