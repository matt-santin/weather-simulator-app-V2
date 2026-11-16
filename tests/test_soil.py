"""ET0 (src.app.domain.et0) and the soil water balance (src.app.domain.soil)
against the worked examples of FAO-56 (Allen et al. 1998), then the water left
in the soil in /api/days on the small store of conftest.py."""

from __future__ import annotations

import shutil
from datetime import date

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.app.api import soil as api_soil
from src.app.api.app import app, get_store
from src.app.domain import et0, soil, thresholds
from src.app.store import PERIODS, Store

GRENOBLE = {"latitude": 45.18, "longitude": 5.72}


def test_example_18_daily_et0_at_uccle() -> None:
    """6 July, 50.80 N, 100 m: every intermediate value FAO prints."""
    tmax, tmin = 21.5, 12.3
    u2 = et0.wind_2m(2.78, 10.0)
    assert u2 == pytest.approx(2.078, abs=0.002)
    assert et0.pressure(100.0) == pytest.approx(100.1, abs=0.05)
    assert et0.slope(16.9) == pytest.approx(0.122, abs=0.0005)
    assert et0.saturation(tmax) == pytest.approx(2.564, abs=0.001)
    assert et0.saturation(tmin) == pytest.approx(1.431, abs=0.001)
    es = (et0.saturation(tmax) + et0.saturation(tmin)) / 2
    ea = (et0.saturation(tmin) * 0.84 + et0.saturation(tmax) * 0.63) / 2  # eq. 17
    assert ea == pytest.approx(1.409, abs=0.001)
    ra = et0.extraterrestrial(50.80, 187)
    assert ra == pytest.approx(41.09, abs=0.05)
    rso = et0.clear_sky(ra, 100.0)
    assert rso == pytest.approx(30.90, abs=0.05)
    rs = 22.07
    rnl = et0.net_longwave(tmax, tmin, ea, rs, rso)
    assert rnl == pytest.approx(3.71, abs=0.03)
    rn = (1 - et0.ALBEDO) * rs - rnl
    assert rn == pytest.approx(13.28, abs=0.03)
    assert et0.reference(tmax, tmin, ea, es, u2, rn, et0.pressure(100.0)) == pytest.approx(3.88, abs=0.02)


def test_example_17_monthly_et0_at_bangkok() -> None:
    """April, with the measured vapour pressure, net radiation and soil heat flux FAO gives."""
    es = (et0.saturation(34.8) + et0.saturation(25.6)) / 2
    assert es == pytest.approx(4.42, abs=0.01)
    assert et0.extraterrestrial(13.73, 105) == pytest.approx(38.06, abs=0.05)
    value = et0.reference(34.8, 25.6, 2.85, es, 2.0, 14.33, et0.pressure(2.0), g=0.14)
    assert value == pytest.approx(5.72, abs=0.02)


def test_example_20_extraterrestrial_radiation_at_lyon() -> None:
    assert et0.extraterrestrial(45.72, 196) == pytest.approx(40.55, abs=0.05)


def test_vapour_from_mean_humidity() -> None:
    es, ea = et0.vapour(21.5, 12.3, 70.0)
    assert ea == pytest.approx(0.7 * es)


def test_polar_night_and_arrays() -> None:
    ra = et0.extraterrestrial(80.0, np.array([1, 172]))
    assert ra[0] == pytest.approx(0.0, abs=1e-9) and ra[1] > 40
    # No sun: taken as overcast, the factor of eq. 39 at its floor (1.35 x 0 - 0.35).
    assert np.isfinite(et0.net_longwave(-20.0, -25.0, 0.1, 0.0, 0.0))
    assert et0.net_longwave(-20.0, -25.0, 0.1, 0.0, 0.0) < 0
    assert et0.reference(-20.0, -25.0, 0.1, 0.1, 2.0, -3.0, 101.3) == 0.0


def test_example_37_stress_coefficient_day_by_day() -> None:
    """Tomato on silt loam: TAW 160 mm, p 0.40, 55 mm missing at the start,
    6 mm/day asked, no rain for 10 days."""
    b = soil.balance(np.zeros(10), np.full(10, 6.0), 160.0, p=0.40, depletion=55.0)
    assert b.ks == pytest.approx([1.00, 1.00, 0.97, 0.91, 0.85, 0.80, 0.75, 0.70, 0.66, 0.62], abs=0.006)
    assert b.eta == pytest.approx([6.0, 6.0, 5.8, 5.4, 5.1, 4.8, 4.5, 4.2, 3.9, 3.7], abs=0.06)
    assert (1 - b.fill) * 160 == pytest.approx([61.0, 67.0, 72.8, 78.3, 83.4, 88.2, 92.6, 96.9, 100.8, 104.5], abs=0.11)


def test_reservoir_overflows_and_never_goes_under_the_wilting_point() -> None:
    wet = soil.balance(np.array([30.0, 0.0]), np.array([2.0, 2.0]), 100.0, depletion=10.0)
    assert wet.fill[0] == 1.0 and wet.drainage[0] == pytest.approx(18.0)
    assert wet.fill[1] == pytest.approx(0.98) and wet.drainage[1] == 0.0
    dry = soil.balance(np.zeros(2000), np.full(2000, 5.0), 100.0)
    assert dry.fill.min() >= 0.0 and dry.fill[-1] < 1e-3 and dry.ks[-1] < 1e-3


def test_a_day_without_data_changes_nothing() -> None:
    b = soil.balance(np.array([0.0, np.nan, 0.0]), np.array([4.0, 4.0, 4.0]), 100.0)
    assert np.isnan(b.fill[1]) and b.fill[2] == pytest.approx(0.92)


def test_snow_is_held_then_given_back_as_melt() -> None:
    start = date(2000, 12, 1)
    tas = np.array([-3.0, -3.0, 1.0, 5.0, 5.0])
    pr = np.array([10.0, 0.0, 0.0, 2.0, 0.0])
    melt = thresholds.SNOW_MELT_MM_PER_DEGREE_DAY
    water = soil.liquid(tas, pr, start)
    assert water[:2].tolist() == [0.0, 0.0]
    assert water[2] == pytest.approx(melt * 1.0)
    assert water[3] == pytest.approx(2.0 + (10.0 - melt))
    assert water[4] == 0.0
    assert water.sum() == pytest.approx(pr.sum())


def days(store: Store, **params) -> list[dict]:
    app.dependency_overrides[get_store] = lambda: store
    try:
        response = TestClient(app).get("/api/days", params=GRENOBLE | params)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    return response.json()["days"]


@pytest.mark.parametrize("source, start, end", [("era5", "1978-03-01", "1978-04-30"), ("cordex", "2051-06-01", "2051-07-31")])
def test_days_carry_the_water_left_in_the_soil(store_path, source, start, end) -> None:
    """The balance runs from the first day of the source, in its own series."""
    store = Store(store_path)
    period = next(p for p in PERIODS if p.source == source)
    cell = store.cell(**GRENOBLE)
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    origin = store.first[source]
    demand, v = api_soil.reference(store, source, cell, origin, last)
    whole = soil.balance(soil.liquid(v["tas"], v["pr"], origin), demand, store.capacity(cell))
    expected = [int(round(100 * f)) for f in whole.fill[(first - origin).days:]]
    got = [d["soil_water"] for d in days(store, start=start, end=end)]
    assert got == expected
    assert all(0 <= w <= 100 for w in got)
    assert api_soil.balance(store, period, cell)[0] == origin


def test_the_soil_dries_when_it_does_not_rain(store_path) -> None:
    """The small store rains its day index: nothing on the first days of each 3000."""
    store = Store(store_path)
    start = date.fromordinal(date(1970, 1, 1).toordinal() + 3000)
    got = [d["soil_water"] for d in days(store, start=start.isoformat(), end=date.fromordinal(start.toordinal() + 4).isoformat())]
    assert got == sorted(got, reverse=True) and got[-1] < got[0]


def test_a_day_without_precipitation_data_counts_as_a_dry_day(store_path) -> None:
    """As for the snow stock: the balance goes on, with no water that day."""
    from tests.conftest import GAP
    got = {d["date"]: d["soil_water"] for d in days(Store(store_path), start="2044-07-13", end="2044-07-15")}
    assert got[GAP.isoformat()] is not None and got[GAP.isoformat()] <= got["2044-07-13"]


def test_a_store_without_solar_radiation_serves_no_soil_water(store_path, tmp_path) -> None:
    path = tmp_path / "point.zarr"
    shutil.copytree(store_path, path)
    shutil.rmtree(path / "cordex" / "rsds")
    store = Store(path)
    assert not store.has("rsds")
    assert all(d["soil_water"] is None for d in days(store, start="2051-06-01", end="2051-06-10"))
    assert all(d["soil_water"] is None for d in days(store, start="1978-03-01", end="1978-03-10"))


def test_many_cells_at_once_give_the_numbers_of_one_cell() -> None:
    """The map store's arithmetic (fill_many, liquid_many) is that of a place."""
    rng = np.random.default_rng(1)
    start = date(1999, 7, 20)
    n, cells = 900, 6
    tas = rng.normal(8.0, 9.0, (n, cells))
    pr = np.where(rng.random((n, cells)) < 0.4, rng.gamma(1.0, 6.0, (n, cells)), 0.0)
    demand = np.maximum(rng.normal(2.5, 1.8, (n, cells)), 0.0)
    tas[100:110, 2] = np.nan
    pr[300:305, 3] = np.nan
    demand[500:503, 4] = np.nan
    capacity = np.array([50.0, 100.0, 150.0, 80.0, 120.0, 300.0])
    water = soil.liquid_many(tas, pr, start)
    fill = soil.fill_many(water, demand, capacity)
    for c in range(cells):
        one = soil.liquid(tas[:, c], pr[:, c], start)
        np.testing.assert_array_equal(water[:, c], one)
        np.testing.assert_array_equal(fill[:, c], soil.balance(one, demand[:, c], capacity[c]).fill)


def test_the_reservoir_is_the_store_s_and_the_constant_where_it_has_none(store_path, tmp_path) -> None:
    from tests.conftest import CAPACITY
    store = Store(store_path)
    assert store.capacity(store.cell(**GRENOBLE)) == CAPACITY
    assert store.capacity(store.cell(45.75, 5.25)) == thresholds.SOIL_CAPACITY_MM
    path = tmp_path / "point.zarr"
    shutil.copytree(store_path, path)
    shutil.rmtree(path / "soil_capacity")
    bare = Store(path)
    assert bare.capacity(bare.cell(**GRENOBLE)) == thresholds.SOIL_CAPACITY_MM
    # The same dry days (the first of a cycle of 3000, conftest.py) take a
    # smaller share of a larger reservoir.
    start = date.fromordinal(date(1970, 1, 1).toordinal() + 3000)
    end = date.fromordinal(start.toordinal() + 9)
    small = [d["soil_water"] for d in days(bare, start=start.isoformat(), end=end.isoformat())]
    large = [d["soil_water"] for d in days(store, start=start.isoformat(), end=end.isoformat())]
    assert all(a >= b for a, b in zip(large, small)) and large[-1] > small[-1]


# --- departure from the normal, for the map (src.store.anomaly) ---------------

def test_the_29th_of_february_takes_the_slot_of_the_28th() -> None:
    from src.store.anomaly import slots
    s = slots(date(2020, 2, 27), 4)  # 27, 28, 29 February, 1 March
    assert s.tolist() == [57, 58, 58, 59]
    assert slots(date(2021, 12, 31), 1).tolist() == [364]
    assert slots(date(2100, 3, 1), 1).tolist() == [59]  # 2100 is not a leap year


def test_the_normal_is_the_mean_of_the_reference_years_and_the_departure_reads_against_it() -> None:
    from src.store.anomaly import FILL, departure, normal
    first = date(1990, 1, 1)
    n = (date(2021, 12, 31) - first).days + 1
    years = (np.datetime64("1990-01-01") + np.arange(n)).astype("datetime64[Y]").astype(int) + 1970
    # Cell 0: 60 % every day of 1991-2020, 0 % outside it (not in the normal).
    # Cell 1: 40 % on even years, 80 % on odd ones (mean 60), and no value on 1 July 2000.
    values = np.stack([np.where((years >= 1991) & (years <= 2020), 60, 0),
                       np.where(years % 2 == 0, 40, 80)], axis=1).astype("uint8")
    values[(date(2000, 7, 1) - first).days, 1] = 255
    base = normal(values, first, 255)
    assert base.shape == (365, 2)
    assert np.allclose(base[:, 0], 60)
    assert np.allclose(base[:, 1], 60, atol=1)  # 29 February and the missing day weigh a little
    out = departure(values, first, 255, base)
    assert out.dtype == np.int8
    assert out[0, 0] == -60  # 1990, outside the normal, read against it
    assert out[(date(2001, 3, 1) - first).days, 1] == 20
    assert out[(date(2000, 7, 1) - first).days, 1] == FILL
