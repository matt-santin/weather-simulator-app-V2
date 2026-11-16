"""Soil water balance, daily: one reservoir per place (FAO-56, chapter 8).

The reservoir holds ``capacity`` mm at most (the available water TAW, between
field capacity and wilting point over the root depth). Rain and snowmelt fill
it, evapotranspiration empties it, what overflows drains away.

While the depletion stays under the readily available water RAW = p x TAW, the
plant takes all the atmosphere asks (Ks = 1, loss = ET0). Past it, Ks falls
linearly to 0 at the wilting point [84] and the loss is Ks x ET0.

The cover is the reference grass (Kc = 1). The same computation for past and
simulated days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from src.app.domain import thresholds

# Fraction of the available water a plant takes without stress: the value
# FAO-56 gives as commonly used. Provisional, like the capacity.
DEPLETION_FRACTION = 0.5


@dataclass(frozen=True)
class Balance:
    fill: np.ndarray  # reservoir at the end of the day, 0 (wilting point) to 1 (field capacity)
    ks: np.ndarray  # water stress coefficient of the day, 1 without stress
    eta: np.ndarray  # actual evapotranspiration, mm
    drainage: np.ndarray  # water lost by overflow, mm


def liquid(tas: np.ndarray, pr: np.ndarray, start: date) -> np.ndarray:
    """Water reaching the soil each day, in mm: rain, and the melt of the snow
    stock. Same stock as src.app.domain.snow (thresholds.SNOW_*): what falls on
    a cold day is kept, each degree above zero melts some, and what is left on
    1 August is dropped. A day without temperature gives its precipitation as
    rain; a day without precipitation gives nothing."""
    days = np.datetime64(start.isoformat()) + np.arange(len(tas))
    months = days.astype("datetime64[M]")
    reset = ((days == months.astype("datetime64[D]"))
             & (months.astype(int) % 12 + 1 == thresholds.SNOW_RESET_MONTH)).tolist()
    stock = 0.0
    out = []
    for t, p, empty in zip(np.asarray(tas, float).tolist(), np.asarray(pr, float).tolist(), reset):
        if empty:
            stock = 0.0
        p = p if p == p else 0.0
        if t != t:  # NaN
            out.append(p)
            continue
        if t < thresholds.SNOW_FALL_C:
            stock += p
            p = 0.0
        melt = min(stock, thresholds.SNOW_MELT_MM_PER_DEGREE_DAY * max(t, 0.0))
        stock -= melt
        out.append(p + melt)
    return np.array(out)


def balance(water: np.ndarray, et0: np.ndarray, capacity: float,
            p: float = DEPLETION_FRACTION, depletion: float = 0.0) -> Balance:
    """The reservoir day by day. ``water`` (see liquid) and ``et0`` in mm, one
    value per day; ``capacity`` in mm; ``depletion`` is the water missing at
    the start, 0 for a full reservoir. Ks is read on the depletion at the start
    of the day, as FAO-56 does. A day without ET0 or water changes nothing and
    is NaN in the result."""
    raw = p * capacity
    n = len(water)
    fill, ks, eta, drainage = (np.full(n, np.nan) for _ in range(4))
    d = float(depletion)
    for i, (w, e) in enumerate(zip(np.asarray(water, float).tolist(), np.asarray(et0, float).tolist())):
        if w != w or e != e:
            continue
        k = 1.0 if d <= raw else (capacity - d) / (capacity - raw)
        d = d + (k * e - w)
        drainage[i] = max(-d, 0.0)
        d = min(max(d, 0.0), capacity)
        fill[i], ks[i], eta[i] = 1.0 - d / capacity, k, k * e
    return Balance(fill, ks, eta, drainage)


# --- the same, many cells at once --------------------------------------------
#
# For the map store (src.store.soil): arrays of days x cells, one numpy step per
# day over every cell. The arithmetic is that of liquid and balance, operation
# for operation, so that a cell gives the same numbers either way
# (tests/test_soil.py). The functions above stay for a single place: on one
# series, plain floats are 20 times faster than numpy.


def liquid_many(tas: np.ndarray, pr: np.ndarray, start: date) -> np.ndarray:
    """liquid, for days x cells."""
    tas, pr = np.asarray(tas, float), np.asarray(pr, float)
    days = np.datetime64(start.isoformat()) + np.arange(tas.shape[0])
    months = days.astype("datetime64[M]")
    reset = ((days == months.astype("datetime64[D]"))
             & (months.astype(int) % 12 + 1 == thresholds.SNOW_RESET_MONTH))
    stock = np.zeros(tas.shape[1:])
    out = np.empty(tas.shape)
    for i in range(tas.shape[0]):
        if reset[i]:
            stock[:] = 0.0
        t = tas[i]
        p = np.where(np.isnan(pr[i]), 0.0, pr[i])
        cold = t < thresholds.SNOW_FALL_C  # False where t is NaN
        stock = stock + np.where(cold, p, 0.0)
        p = np.where(cold, 0.0, p)
        with np.errstate(invalid="ignore"):
            melt = np.minimum(stock, thresholds.SNOW_MELT_MM_PER_DEGREE_DAY * np.maximum(t, 0.0))
        melt = np.where(np.isnan(t), 0.0, melt)
        stock = stock - melt
        out[i] = p + melt
    return out


def fill_many(water: np.ndarray, et0: np.ndarray, capacity, p: float = DEPLETION_FRACTION) -> np.ndarray:
    """balance(...).fill, for days x cells, starting full. ``capacity`` in mm,
    one value or one per cell."""
    water, et0 = np.asarray(water, float), np.asarray(et0, float)
    capacity = np.broadcast_to(np.asarray(capacity, float), water.shape[1:])
    raw = p * capacity
    d = np.zeros(water.shape[1:])
    out = np.full(water.shape, np.nan)
    for i in range(water.shape[0]):
        w, e = water[i], et0[i]
        ok = ~(np.isnan(w) | np.isnan(e))
        k = np.where(d <= raw, 1.0, (capacity - d) / (capacity - raw))
        with np.errstate(invalid="ignore"):
            nxt = np.minimum(np.maximum(d + (k * e - w), 0.0), capacity)
        d = np.where(ok, nxt, d)
        out[i] = np.where(ok, 1.0 - d / capacity, np.nan)
    return out
