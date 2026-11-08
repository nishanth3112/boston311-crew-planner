import numpy as np
import pandas as pd
import pytest

from boston311.forecast import backtest as bt
from boston311.forecast.models import (
    damped_ets,
    load_forecast,
    naive_yoy,
    seasonal_naive,
)


def _series(values, start="2023-01") -> pd.Series:
    months = pd.period_range(start, periods=len(values), freq="M").strftime("%Y-%m")
    return pd.Series(values, index=months, dtype=float)


def test_seasonal_naive_repeats_the_same_months_a_year_earlier():
    history = _series(range(1, 19))  # Jan 2023 = 1 ... Jun 2024 = 18
    assert seasonal_naive(history, 6).tolist() == [7, 8, 9, 10, 11, 12]  # Jul-Dec 2023


def test_naive_yoy_scales_by_growth_over_the_overlapping_months():
    # Jan-Jun 2023 sum to 60, Jan-Jun 2024 to 90: growth 1.5, applied to Jul-Dec 2023
    history = _series([10] * 6 + [20] * 6 + [15] * 6)
    assert naive_yoy(history, 3).tolist() == [30, 30, 30]
    # with 24 months the growth is the full year: 2024 total 240 over 2023 total 120,
    # applied to Jan-Feb 2024 (20 each)
    assert naive_yoy(_series([10] * 12 + [20] * 12), 2).tolist() == [40, 40]


def test_damped_ets_keeps_a_flat_seasonal_pattern():
    # the same seasonal shape every year and no trend: the forecast is that shape again
    shape = np.array([0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 1.6, 1.4, 1.1, 0.9, 0.8, 0.6])
    history = _series(np.tile(shape * 1000, 2))
    assert damped_ets(history, 12) == pytest.approx(shape * 1000, rel=1e-3)


def test_damped_ets_fits_fewer_than_24_months_with_the_right_months():
    # the backtest case: Jan 2023 to Jun 2024, forecasting Jul-Dec. With a repeating
    # pattern the forecast must be Jul-Dec of that pattern, not shifted by a month.
    shape = np.array([0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 1.6, 1.4, 1.1, 0.9, 0.8, 0.6]) * 1000
    history = _series(np.tile(shape, 2)[:18])
    assert damped_ets(history, 6) == pytest.approx(shape[6:], rel=1e-3)


def test_methods_reject_inputs_they_cannot_forecast():
    with pytest.raises(ValueError, match="at most 12"):
        seasonal_naive(_series([1.0] * 24), 13)
    with pytest.raises(ValueError, match="more than 12 months"):
        naive_yoy(_series([1.0] * 12), 3)


def test_backtest_trains_through_june_2024_and_scores_july_to_december():
    # 2023: 100 a month; 2024: 100 to June, then 200. Seasonal naive predicts the 2023
    # values (100) for Jul-Dec 2024, so every test month is 50% off. Anything after
    # December 2024 must be ignored.
    values = [100.0] * 18 + [200.0] * 6 + [999.0] * 9
    series = pd.DataFrame({"X": values}, index=_series(values).index)
    results = bt.backtest(series).set_index("method")
    assert results.loc["seasonal_naive", "mape"] == pytest.approx(0.5)
    assert results.loc["seasonal_naive", "rmspe"] == pytest.approx(0.5)


def test_check_2025_reports_bias_hits_and_totals():
    index = _series([0.0] * 33).index  # Jan 2023 to Sep 2025
    series = pd.DataFrame({"X": [0.0] * 24 + [100.0] * 9}, index=index)
    series = series.rename_axis(index="month", columns="department")  # as monthly_series()
    forecast = pd.DataFrame(
        {
            "department": "X",
            "month": [f"2025-{m:02d}" for m in range(1, 10)],
            "forecast": [120.0] * 9,
            "lower": [110.0] * 4 + [90.0] * 5,  # 5 of 9 intervals contain 100
            "upper": [130.0] * 9,
        }
    )
    row = bt.check_2025(series, forecast).iloc[0]
    assert row["bias"] == pytest.approx(0.2)  # forecast 20% high
    assert row["inside_80"] == pytest.approx(5 / 9)
    assert row["actual_vs_forecast"] == pytest.approx(100 / 120)


def test_choose_takes_lowest_mape_and_breaks_exact_ties_by_simplicity():
    results = pd.DataFrame(
        {
            "department": ["A"] * 3 + ["B"] * 3,
            "method": ["damped_ets", "naive_yoy", "seasonal_naive"] * 2,
            "mape": [0.05, 0.10, 0.20, 0.10, 0.10, 0.30],
            "rmspe": [0.0] * 6,
        }
    )
    chosen = bt.choose(results).set_index("department")["method"]
    assert chosen.to_dict() == {"A": "damped_ets", "B": "naive_yoy"}


def test_forecast_interval_is_the_rms_error_band_clipped_at_zero():
    series = pd.DataFrame({"X": [100.0] * 24}, index=_series([0] * 24).index)
    chosen = pd.DataFrame(
        {"department": ["X"], "method": ["seasonal_naive"], "mape": [0.5], "rmspe": [1.0]}
    )
    row = bt.forecast_2025(series, chosen).iloc[0]
    assert row["month"] == "2025-01"
    assert row["forecast"] == 100
    assert row["upper"] == pytest.approx(100 * (1 + 1.2816), abs=0.1)
    assert row["lower"] == 0  # 100 x (1 - 1.2816) is negative


def test_load_forecast_returns_all_four_departments_for_2025():
    result = load_forecast()
    assert [d.department for d in result.departments] == ["PWDx", "BTDT", "PARK", "ISD"]
    for d in result.departments:
        assert [m.month for m in d.months] == [f"2025-{m:02d}" for m in range(1, 13)]
        assert all(m.lower <= m.forecast <= m.upper for m in d.months)
        assert 0 < d.backtest_mape < 1
    assert [d.department for d in load_forecast(["ISD"]).departments] == ["ISD"]
