"""Reference evapotranspiration ET0, daily, FAO Penman-Monteith (Allen et al.
1998, FAO Irrigation and Drainage Paper 56, equation numbers in brackets).

What a well-watered reference grass (0.12 m high, surface resistance 70 s/m,
albedo 0.23) would evaporate under the weather of the day, in mm/day. It
depends on the weather only, never on the soil or on the real plant.

Every function takes floats or arrays. Temperatures in deg C, pressures in
kPa, radiation in MJ m-2 day-1, wind in m/s.
"""

from __future__ import annotations

import numpy as np

# 1 W m-2 over a day, in MJ m-2 (FAO-56, table 3).
MJ_PER_W = 0.0864
# Stefan-Boltzmann constant, MJ K-4 m-2 day-1 (FAO-56, eq. 39).
SIGMA = 4.903e-9
# Albedo of the reference grass (FAO-56, eq. 38).
ALBEDO = 0.23


def saturation(t):
    """Saturation vapour pressure at temperature ``t`` [11]."""
    t = np.asarray(t, float)
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def slope(t):
    """Slope of the saturation vapour pressure curve, kPa per deg C [13]."""
    t = np.asarray(t, float)
    return 4098.0 * saturation(t) / (t + 237.3) ** 2


def pressure(altitude):
    """Atmospheric pressure at ``altitude`` in m, standard atmosphere [7]."""
    return 101.3 * ((293.0 - 0.0065 * np.asarray(altitude, float)) / 293.0) ** 5.26


def wind_2m(speed, height: float = 10.0):
    """Wind speed at 2 m from the speed measured at ``height`` m [47]."""
    return np.asarray(speed, float) * 4.87 / np.log(67.8 * height - 5.42)


def vapour(tmax, tmin, hurs):
    """Mean saturation vapour pressure [12] and actual vapour pressure from the
    daily mean relative humidity in % [19]."""
    es = (saturation(tmax) + saturation(tmin)) / 2.0
    return es, es * np.asarray(hurs, float) / 100.0


def extraterrestrial(latitude: float, day_of_year):
    """Radiation at the top of the atmosphere on a horizontal surface [21],
    ``latitude`` in degrees, north positive. Zero in the polar night."""
    j = np.asarray(day_of_year, float)
    phi = np.radians(latitude)
    distance = 1.0 + 0.033 * np.cos(2.0 * np.pi * j / 365.0)  # [23]
    declination = 0.409 * np.sin(2.0 * np.pi * j / 365.0 - 1.39)  # [24]
    sunset = np.arccos(np.clip(-np.tan(phi) * np.tan(declination), -1.0, 1.0))  # [25]
    return (24.0 * 60.0 / np.pi) * 0.0820 * distance * (
        sunset * np.sin(phi) * np.sin(declination)
        + np.cos(phi) * np.cos(declination) * np.sin(sunset))


def clear_sky(ra, altitude):
    """Solar radiation a cloudless day would give at the surface [37]."""
    return (0.75 + 2e-5 * np.asarray(altitude, float)) * ra


def net_longwave(tmax, tmin, ea, rs, rso):
    """Net outgoing longwave radiation, FAO estimate from the temperatures,
    the vapour pressure and the cloudiness read in rs / rso [39]. A day
    without sun (rso = 0) is taken as overcast."""
    tmax, tmin = np.asarray(tmax, float) + 273.16, np.asarray(tmin, float) + 273.16
    rs, rso = np.asarray(rs, float), np.asarray(rso, float)
    ratio = np.clip(np.divide(rs, rso, out=np.zeros(np.broadcast(rs, rso).shape), where=rso > 0), 0.0, 1.0)
    return (SIGMA * (tmax ** 4 + tmin ** 4) / 2.0
            * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * ratio - 0.35))


def reference(tmax, tmin, ea, es, u2, rn, pressure_kpa, g=0.0):
    """ET0 in mm/day [6]. ``rn`` is the net radiation at the surface, ``g`` the
    soil heat flux, negligible over a day [42]. Never negative."""
    t = (np.asarray(tmax, float) + np.asarray(tmin, float)) / 2.0
    delta = slope(t)
    gamma = 0.665e-3 * np.asarray(pressure_kpa, float)  # [8]
    u2 = np.asarray(u2, float)
    et0 = ((0.408 * delta * (np.asarray(rn, float) - g)
            + gamma * 900.0 / (t + 273.0) * u2 * (es - ea))
           / (delta + gamma * (1.0 + 0.34 * u2)))
    return np.maximum(et0, 0.0)
