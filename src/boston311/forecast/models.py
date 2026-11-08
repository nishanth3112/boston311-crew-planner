"""Monthly demand forecasts: three methods, and the 2025 forecast the planner and API read."""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from boston311.api.schemas import Department, DepartmentForecast, ForecastMonth, ForecastResult
from boston311.config import PROCESSED_DIR

FORECAST_PATH = PROCESSED_DIR / "forecast_2025.parquet"
SEASON = 12


def seasonal_naive(history: pd.Series, horizon: int) -> np.ndarray:
    """Each month gets the value of the same month a year earlier (horizon <= 12)."""
    if horizon > SEASON:
        raise ValueError(f"seasonal naive forecasts at most {SEASON} months, not {horizon}")
    start = len(history) - SEASON
    return history.to_numpy(float)[start : start + horizon]


def naive_yoy(history: pd.Series, horizon: int) -> np.ndarray:
    """Seasonal naive scaled by year-over-year growth: the last n months over the same n months
    a year earlier, with n = min(12, months - 12)."""
    values = history.to_numpy(float)
    n = min(SEASON, len(values) - SEASON)
    if n < 1:
        raise ValueError("naive x YoY needs more than 12 months of history")
    growth = values[-n:].sum() / values[-n - SEASON : -SEASON].sum()
    return seasonal_naive(history, horizon) * growth


def damped_ets(history: pd.Series, horizon: int) -> np.ndarray:
    """Damped additive-trend ETS on deseasonalized demand, then reseasonalized.

    Seasonal indices (month / that year's monthly mean) come from the latest full calendar
    year in history, so the method works on fewer than 24 months. history is indexed by
    "YYYY-MM" strings.
    """
    months = pd.PeriodIndex(history.index, freq="M")
    full_years = [y for y in sorted(set(months.year)) if (months.year == y).sum() == SEASON]
    base = history[months.year == full_years[-1]]
    index = base.to_numpy(float) / base.mean()  # position 0 is January
    adjusted = history.to_numpy(float) / index[months.month - 1]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        fit = ExponentialSmoothing(
            adjusted, trend="add", damped_trend=True, initialization_method="estimated"
        ).fit()
    future = pd.period_range(months[-1] + 1, periods=horizon, freq="M")
    return fit.forecast(horizon) * index[future.month - 1]


METHODS = {  # simplest first: on an exact backtest tie, the earlier method wins
    "seasonal_naive": seasonal_naive,
    "naive_yoy": naive_yoy,
    "damped_ets": damped_ets,
}


def load_forecast(departments: list[Department] | None = None) -> ForecastResult:
    """Monthly 2025 forecast with 80% interval; all four departments when None."""
    # read on every call (48 rows), so a rebuilt forecast shows up without a restart
    table = pd.read_parquet(FORECAST_PATH)
    result = []
    for department, rows in table.groupby("department", sort=False):
        if departments and department not in departments:
            continue
        months = [
            ForecastMonth(month=r.month, forecast=r.forecast, lower=r.lower, upper=r.upper)
            for r in rows.itertuples()
        ]
        mape = float(rows["backtest_mape"].iloc[0])
        result.append(DepartmentForecast(department=department, months=months, backtest_mape=mape))
    return ForecastResult(departments=result)
