"""The correction by quantiles (src.correction.qdm), on made-up series whose
answer is known.

No file is read: these tests call the functions that compute (quantiles, rank,
calibrate, correct), with a reference and a model drawn here. They say whether
the code does what the method says, not whether the method is right: that is
the work of src.validation, against observations.

One calendar month, a few points. The reference and the model of the
calibration period have the same number of days, as on the drive.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.correction import derive, qdm
from src.correction.qdm import DAY, MIN_WET, NQ, VARS, calibrate, correct, quantiles, rank, window

POINTS = 4
CAL_DAYS = 45 * 31  # a 31-day month over the 45 years of the calibration
WINDOW_DAYS = qdm.WINDOW * 31


def temperatures(rng, days: int, mean: float = 290.0, spread: float = 4.0) -> np.ndarray:
    return (mean + spread * rng.standard_normal((days, POINTS))).astype("float32")


def rain(rng, days: int, dry: float, scale: float) -> np.ndarray:
    """Daily rain in kg m-2 s-1: a share `dry` of days under 1 mm (a drizzle of
    0 to 0.8 mm), the others 1 mm plus a gamma of mean 2 x scale mm."""
    wet = rng.random((days, POINTS)) >= dry
    amount = np.where(wet, 1.0 + rng.gamma(2.0, scale, (days, POINTS)),
                      0.8 * rng.random((days, POINTS)))
    return (amount / DAY).astype("float32")


# --- the pieces ----------------------------------------------------------------


def test_quantiles_are_those_of_numpy_gaps_left_out() -> None:
    rng = np.random.default_rng(1)
    x = temperatures(rng, 500)
    x[rng.random(x.shape) < 0.2] = np.nan
    x[:, 3] = np.nan  # a point without any value, as the sea on the 0.1 deg grid
    ours = quantiles(x)
    assert ours.shape == (NQ, POINTS)
    assert np.allclose(ours[:, :3], np.nanquantile(x[:, :3].astype("float64"), qdm.LEVELS, axis=0), atol=1e-3)
    assert np.isnan(ours[:, 3]).all()


def test_a_value_tied_with_several_quantiles_takes_the_middle_of_them() -> None:
    # 30 % of days without a cloud: the quantiles 0 to 29 are all 0.
    q = np.concatenate([np.zeros(30), np.linspace(1, 100, NQ - 30)])[:, None].astype("float32")
    x = np.array([[0.0], [100.0], [-5.0], [500.0]], dtype="float32")
    assert rank(x, q)[:, 0] == pytest.approx([14.5, NQ - 1, 0, NQ - 1])


def test_the_window_is_30_years_around_the_year_held_inside_the_series() -> None:
    assert window(2050) == (2035, 2064)
    assert window(1970) == (1970, 1999)
    assert window(2100) == (2071, 2100)


# --- additive form: the temperatures --------------------------------------------


def test_a_model_without_bias_comes_out_unchanged() -> None:
    rng = np.random.default_rng(2)
    ref = temperatures(rng, CAL_DAYS)
    cal = calibrate(ref, ref.copy(), VARS["tas"])
    future = temperatures(rng, WINDOW_DAYS, mean=293.0)
    assert np.array_equal(correct(future[:31], future, cal, VARS["tas"]), future[:31])


def test_a_constant_bias_is_removed_everywhere_beyond_the_known_values_too() -> None:
    rng = np.random.default_rng(3)
    ref = temperatures(rng, CAL_DAYS)
    cal = calibrate(ref, ref + 2.0, VARS["tasmax"])
    future = temperatures(rng, WINDOW_DAYS, mean=296.0)
    days = future[:31].copy()
    days[0], days[1] = 340.0, 230.0  # far beyond every quantile: the extreme one applies
    assert np.allclose(correct(days, future, cal, VARS["tasmax"]), days - 2.0, atol=1e-3)


def test_the_change_the_model_gives_is_kept_and_the_bias_of_each_quantile_removed() -> None:
    """A model too warm by 2 K and twice too variable, which warms by 3 K: once
    corrected, the reference plus 3 K, day for day, between its extreme
    quantiles (0.5 % and 99.5 %)."""
    rng = np.random.default_rng(4)
    ref = temperatures(rng, CAL_DAYS)
    hist = (290.0 + 2.0 + 2.0 * (ref - 290.0)).astype("float32")
    cal = calibrate(ref, hist, VARS["tas"])
    future = hist + 3.0  # the same days, 3 K warmer: the window of a later year
    fixed = correct(future, future, cal, VARS["tas"])
    assert np.allclose(fixed.mean(0), ref.mean(0) + 3.0, atol=0.01)
    low, high = quantiles(future)[[0, -1]]
    inside = (future >= low) & (future <= high)
    assert inside.mean() > 0.98
    assert np.abs(fixed - (ref + 3.0))[inside].max() < 1e-3


def test_beyond_the_extreme_quantiles_the_correction_of_the_extreme_quantile_applies() -> None:
    """The hottest and coldest 0.5 % of the days of a window: what they exceed
    the extreme quantile by is the model's own, not rescaled. With a model twice
    too variable the corrected series is therefore a little too spread (1 to
    2 % here), and its records too far out: a property of the method, kept under
    watch, not a fault."""
    rng = np.random.default_rng(4)
    ref = temperatures(rng, CAL_DAYS)
    hist = (290.0 + 2.0 + 2.0 * (ref - 290.0)).astype("float32")
    cal = calibrate(ref, hist, VARS["tas"])
    fixed = correct(hist, hist, cal, VARS["tas"])
    bias = cal["ref"] - cal["hist"]
    low, high = cal["hist"][[0, -1]]
    for beyond, b in ((hist > high, bias[-1]), (hist < low, bias[0])):
        assert beyond.any()
        assert np.allclose((fixed - hist)[beyond], np.broadcast_to(b, hist.shape)[beyond], atol=1e-3)
    assert 1.0 < (fixed.std(0) / ref.std(0)).max() < 1.02


def test_a_gap_stays_a_gap_and_a_point_without_values_spoils_no_other() -> None:
    rng = np.random.default_rng(5)
    ref, hist, future = (temperatures(rng, n, m) for n, m in
                         ((CAL_DAYS, 290.0), (CAL_DAYS, 291.5), (WINDOW_DAYS, 294.0)))
    whole = correct(future[:31], future, calibrate(ref, hist, VARS["tas"]), VARS["tas"])
    for a in (ref, hist, future):
        a[:, 2] = np.nan  # the sea
    days = future[:31].copy()
    days[7, 0] = np.nan  # one missing day
    holed = correct(days, future, calibrate(ref, hist, VARS["tas"]), VARS["tas"])
    assert np.isnan(holed[:, 2]).all() and np.isnan(holed[7, 0])
    keep = np.ones(holed.shape, bool)
    keep[:, 2], keep[7, 0] = False, False
    assert np.array_equal(holed[keep], whole[keep])


def test_corrected_values_stay_inside_the_bounds_of_the_variable() -> None:
    """Relative humidity. A model 22 points too dry that turns 25 points more
    humid: its bias would carry days past 100 %. A model 20 points too humid
    that dries by 25 points: below 0 %. Both are stopped at the bound."""
    rng = np.random.default_rng(6)

    def humidity(mean: float, spread: float) -> np.ndarray:
        return np.clip(mean + spread * rng.standard_normal((CAL_DAYS, POINTS)), 0, 100).astype("float32")

    for ref, hist, shift, bound in ((humidity(92, 8), humidity(70, 15), 25.0, 100.0),
                                    (humidity(10, 8), humidity(30, 15), -25.0, 0.0)):
        cal = calibrate(ref, hist, VARS["hurs"])
        future = np.clip(hist + shift, 0, 100).astype("float32")
        fixed = correct(future, future, cal, VARS["hurs"])
        assert fixed.min() >= 0.0 and fixed.max() <= 100.0
        assert (fixed == bound).mean() > 0.05  # many days stopped at the bound


def test_where_only_the_mean_is_corrected_every_day_moves_by_the_same_amount() -> None:
    """Surface pressure in winter (Var.mean_only): the gap between the means,
    whatever the day, although the model is twice too variable."""
    rng = np.random.default_rng(7)
    ref = (101000.0 + 800.0 * rng.standard_normal((CAL_DAYS, POINTS))).astype("float32")
    hist = (101300.0 + 1600.0 * rng.standard_normal((CAL_DAYS, POINTS))).astype("float32")
    v = VARS["ps"]
    winter = correct(hist, hist, calibrate(ref, hist, v, month=1), v)
    shift = winter.astype("float64") - hist
    assert np.allclose(shift, ref.mean(0, dtype="float64") - hist.mean(0, dtype="float64"), atol=0.5)
    summer = correct(hist, hist, calibrate(ref, hist, v, month=7), v)
    assert (summer - hist).std(0).min() > 100.0  # the full correction: the spread is put right too


# --- multiplicative form --------------------------------------------------------


def test_the_multiplicative_form_keeps_the_ratio_the_model_gives() -> None:
    """A wind twice too strong, which strengthens by 20 %: the reference times 1.2."""
    rng = np.random.default_rng(8)
    ref = rng.gamma(4.0, 1.0, (CAL_DAYS, POINTS)).astype("float32") + 0.5
    cal = calibrate(ref, 2.0 * ref, VARS["sfcWind"])
    future = (2.4 * ref).astype("float32")
    fixed = correct(future, future, cal, VARS["sfcWind"])
    assert np.allclose(fixed.mean(0), 1.2 * ref.mean(0), rtol=0.005)
    assert np.allclose(fixed, 1.2 * ref, rtol=0.05)


# --- precipitation: occurrence, then intensity ----------------------------------


def test_the_model_gets_the_share_of_dry_days_of_the_reference() -> None:
    """A model that rains too often and too little: 35 % of dry days where the
    reference has 60 %."""
    rng = np.random.default_rng(9)
    v = VARS["pr"]
    ref, hist = rain(rng, CAL_DAYS, dry=0.60, scale=3.0), rain(rng, CAL_DAYS, dry=0.35, scale=1.0)
    cal = calibrate(ref, hist, v)
    assert np.allclose((hist < cal["threshold"]).mean(0), (ref < v.wet).mean(0), atol=1.5 / CAL_DAYS)
    fixed = correct(hist, hist, cal, v)
    assert np.allclose((fixed < v.wet).mean(0), (ref < v.wet).mean(0), atol=0.005)
    # The days made dry carry the drizzle of the reference, never more than it.
    made_dry = hist < cal["threshold"]
    assert fixed[made_dry].max() <= np.where(ref < v.wet, ref, 0).max() + 1e-12
    assert fixed.min() >= 0.0
    # And the total is the one of the reference: wet days by their quantiles,
    # dry days by its drizzle.
    assert np.allclose(fixed.sum(0), ref.sum(0), rtol=0.02)


def test_the_change_in_rain_the_model_gives_is_kept_wet_days_and_their_quantiles() -> None:
    """Every day 30 % wetter in the model. What the correction keeps: the change
    in the number of wet days (the threshold is the one of the calibration), and
    the change of each quantile of the wet days. What it does not keep: the
    change of the total. A model day that crosses the threshold becomes a wet
    day of the reference, which rains more per wet day here: +30 % in the model
    comes out near +48 %. The same mechanism amplifies a drying (the summer
    drying of docs/correction.md, section 10)."""
    rng = np.random.default_rng(10)
    v = VARS["pr"]
    ref, hist = rain(rng, CAL_DAYS, dry=0.60, scale=3.0), rain(rng, CAL_DAYS, dry=0.35, scale=1.0)
    cal = calibrate(ref, hist, v)
    th = cal["threshold"]
    now = correct(hist, hist, cal, v)
    wetter = (1.3 * hist).astype("float32")
    later = correct(wetter, wetter, cal, v)

    def wet_quantiles(x, wet):
        return quantiles(np.where(x >= wet, x, np.nan))

    assert (later >= v.wet).sum() / (now >= v.wet).sum() == pytest.approx(
        (wetter >= th).sum() / (hist >= th).sum(), rel=0.005)
    model = wet_quantiles(wetter, th) / wet_quantiles(hist, th)
    corrected = wet_quantiles(later, v.wet) / wet_quantiles(now, v.wet)
    assert np.allclose(corrected, model, rtol=0.03)
    assert later.sum() / now.sum() == pytest.approx(1.48, abs=0.03)


def test_a_model_drier_than_the_reference_keeps_all_its_wet_days() -> None:
    """More days at exactly 0 than the reference has dry days: the threshold is
    its smallest positive value, and it stays too dry."""
    rng = np.random.default_rng(11)
    v = VARS["pr"]
    ref = rain(rng, CAL_DAYS, dry=0.30, scale=3.0)
    hist = rain(rng, CAL_DAYS, dry=0.0, scale=3.0)
    hist[rng.random(hist.shape) < 0.70] = 0.0
    cal = calibrate(ref, hist, v)
    assert np.array_equal(cal["threshold"], np.where(hist > 0, hist, np.inf).min(0))
    fixed = correct(hist, hist, cal, v)
    assert ((fixed >= v.wet) == (hist > 0)).mean() > 0.995


def test_with_too_few_wet_days_to_calibrate_the_wet_days_keep_their_raw_amount() -> None:
    rng = np.random.default_rng(12)
    v = VARS["pr"]
    ref = rain(rng, CAL_DAYS, dry=1.0, scale=3.0)  # a desert in summer
    ref[:MIN_WET - 1, :] = 5.0 / DAY
    hist = rain(rng, CAL_DAYS, dry=0.90, scale=3.0)
    cal = calibrate(ref, hist, v)
    assert (cal["n_ref"] < MIN_WET).all()
    fixed = correct(hist, hist, cal, v)
    wet = hist >= cal["threshold"]
    assert np.array_equal(fixed[wet], hist[wet])


# --- the derived fields ---------------------------------------------------------


def test_days_with_the_minimum_above_the_maximum_are_swapped_once(monkeypatch) -> None:
    import xarray as xr
    tx = xr.DataArray(np.array([[20.0, 15.0], [18.0, np.nan]]), dims=("time", "cell"), name="tasmax")
    tn = xr.DataArray(np.array([[10.0, 16.0], [18.0, 3.0]]), dims=("time", "cell"), name="tasmin")
    files = {"tasmax": tx, "tasmin": tn}
    monkeypatch.setattr(derive, "corrected", lambda name, year: files[name].copy())
    monkeypatch.setattr(derive, "write", lambda da, year: files.__setitem__(da.name, da))
    assert derive.tn_tx(2050) == 1
    assert files["tasmax"].values[0, 1] == 16.0 and files["tasmin"].values[0, 1] == 15.0
    assert np.isnan(files["tasmax"].values[1, 1]) and files["tasmin"].values[1, 1] == 3.0
    assert derive.tn_tx(2050) == 0  # running it again changes nothing


def test_specific_humidity_rebuilt_from_relative_humidity_temperature_and_pressure(monkeypatch) -> None:
    """Saturated air at 20 deg C and 1013.25 hPa: q = 0.622 e / (p - 0.378 e), with
    a saturation vapour pressure e near 2 337 Pa, gives 14.5 g of vapour per kg."""
    import xarray as xr
    fields = {"hurs": [100.0, 50.0, 0.0], "tas": [293.15] * 3, "ps": [101325.0] * 3}
    written = {}
    monkeypatch.setattr(derive, "corrected",
                        lambda name, year: xr.DataArray(np.array(fields[name], "float32"), dims="time", name=name))
    monkeypatch.setattr(derive, "write", lambda da, year: written.__setitem__(da.name, da))
    derive.huss(2050)
    q = written["huss"].values
    assert q[0] == pytest.approx(0.01448, rel=0.005)
    assert q[1] == pytest.approx(q[0] / 2, rel=0.01) and q[2] == 0.0
