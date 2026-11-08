"""Backtest the forecast methods and write data/processed/forecast_2025.parquet."""

from boston311.forecast import backtest as bt
from boston311.forecast.models import FORECAST_PATH

series = bt.monthly_series()
results = bt.backtest(series)
chosen = bt.choose(results)
forecast = bt.forecast_2025(series, chosen)
forecast.to_parquet(FORECAST_PATH, index=False)

print(results.pivot(index="department", columns="method", values="mape").round(4))
print(chosen.set_index("department")[["method", "mape", "rmspe"]].round(4))
print(bt.check_2025(series, forecast).round(3))
print(f"{FORECAST_PATH.name}: {len(forecast)} rows")
