"""Backtest the forecast methods, pick one per department, and build the 2025 forecast.

Train on January 2023 to June 2024, test on July to December 2024. Each department gets the
method with the lowest MAPE, refit on all of 2023-2024. The January to September 2025
actuals are only a check: they never pick a method or enter a fit.
"""

import numpy as np
import pandas as pd

from boston311.config import DEPARTMENTS, PROCESSED_DIR
from boston311.forecast.models import METHODS

TRAIN = ("2023-01", "2024-06")
TEST = ("2024-07", "2024-12")
HISTORY = ("2023-01", "2024-12")
CHECK = ("2025-01", "2025-09")
Z_80 = 1.2816  # two-sided 80% normal interval


def monthly_series() -> pd.DataFrame:
    """Requests per month (rows, "YYYY-MM") by department (columns), January 2023 onward."""
    monthly = pd.read_csv(PROCESSED_DIR / "monthly_demand.csv")
    table = monthly.pivot(index="month", columns="department", values="requests")
    return table[list(DEPARTMENTS)]


def _pct_errors(predicted: np.ndarray, actual: np.ndarray) -> np.ndarray:
    return (predicted - actual) / actual


def backtest(series: pd.DataFrame) -> pd.DataFrame:
    """One row per department and method: MAPE and RMS % error on the test months."""
    actual = series.loc[TEST[0] : TEST[1]]
    rows = []
    for department in series.columns:
        train = series.loc[TRAIN[0] : TRAIN[1], department]
        for method, model in METHODS.items():
            errors = _pct_errors(model(train, len(actual)), actual[department].to_numpy(float))
            rows.append(
                {
                    "department": department,
                    "method": method,
                    "mape": float(np.abs(errors).mean()),
                    "rmspe": float(np.sqrt((errors**2).mean())),
                }
            )
    return pd.DataFrame(rows)


def choose(results: pd.DataFrame) -> pd.DataFrame:
    """Each department's lowest-MAPE method; an exact tie goes to the simpler method."""
    order = results["method"].map(list(METHODS).index)
    ranked = results.assign(order=order).sort_values(["department", "mape", "order"])
    return ranked.groupby("department", sort=False).head(1).drop(columns="order")


def forecast_2025(series: pd.DataFrame, chosen: pd.DataFrame) -> pd.DataFrame:
    """Monthly 2025 forecast per department from its chosen method, refit on 2023-2024, with
    an 80% interval of forecast x (1 +/- 1.2816 x backtest RMS % error)."""
    months = [f"2025-{m:02d}" for m in range(1, 13)]
    rows = []
    for c in chosen.set_index("department").loc[list(series.columns)].itertuples():
        history = series.loc[HISTORY[0] : HISTORY[1], c.Index]
        point = METHODS[c.method](history, len(months))
        half = Z_80 * c.rmspe
        for month, value in zip(months, point, strict=True):
            rows.append(
                {
                    "department": c.Index,
                    "month": month,
                    "forecast": round(float(value), 1),
                    "lower": round(max(0.0, value * (1 - half)), 1),
                    "upper": round(float(value * (1 + half)), 1),
                    "method": c.method,
                    "backtest_mape": round(c.mape, 4),
                }
            )
    return pd.DataFrame(rows)


def check_2025(series: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
    """The 2025 forecast against January-September 2025 actuals: MAPE, bias (mean of
    (forecast - actual) / actual), interval hits, and total actual over total forecast."""
    actual = series.loc[CHECK[0] : CHECK[1]].reset_index().melt("month", value_name="actual")
    merged = forecast.merge(actual, on=["department", "month"])
    merged["error"] = _pct_errors(merged["forecast"], merged["actual"])
    merged["inside"] = merged["actual"].between(merged["lower"], merged["upper"])
    return (
        merged.groupby("department", sort=False)
        .agg(
            months=("month", "size"),
            mape=("error", lambda e: e.abs().mean()),
            bias=("error", "mean"),
            inside_80=("inside", "mean"),
            actual=("actual", "sum"),
            forecast=("forecast", "sum"),
        )
        .assign(actual_vs_forecast=lambda t: t["actual"] / t["forecast"])
        .drop(columns=["actual", "forecast"])
        .reset_index()
    )
