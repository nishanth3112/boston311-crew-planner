"""Daily queue simulator: replays a year of requests to score a crew plan.

A deterministic fluid model: each day's arrivals split into target windows by the 2024 mix
(sla_profile.csv) instead of sampling one target per request. Crews work weekdays, requests
arrive every day, and the queue is first in, first out by arrival day.
"""

from collections import deque

import numpy as np
import pandas as pd

from boston311.config import (
    DEPARTMENTS,
    LATE_30_DAYS_PENALTY,
    OVERDUE_PENALTY,
    PROCESSED_DIR,
    WORK_DAYS_PER_MONTH,
)

YEAR_DAYS = pd.date_range("2025-01-01", "2025-12-31")
# stylized shocks: daily arrivals multiplied inside the window, by department
SHOCKS = {
    "snowstorm": {
        "start": "2025-02-03",
        "end": "2025-02-09",
        "factors": {"PWDx": 3.0, "BTDT": 1.5},
    },
    "heat_wave": {"start": "2025-07-14", "end": "2025-07-20", "factors": {"PARK": 2.0, "ISD": 2.0}},
}


def sla_shares(code: str) -> pd.DataFrame:
    """target_days (NaN = no target) and share of the department's 2024 requests."""
    table = pd.read_csv(PROCESSED_DIR / "sla_profile.csv")
    return table.loc[table["department"] == code, ["target_days", "share"]]


def _weekday_weights(code: str) -> pd.Series:
    """2024 mean requests by day of week (0 = Monday), relative to the overall mean."""
    days = pd.read_csv(PROCESSED_DIR / "daily_profile.csv", parse_dates=["date"])
    days = days[(days["department"] == code) & (days["date"].dt.year == 2024)]
    by_weekday = days.groupby(days["date"].dt.day_of_week)["requests"].mean()
    return by_weekday / by_weekday.mean()


def daily_arrivals(
    code: str, monthly: dict[str, float], multiplier: float = 1.0, shock: str = "none"
) -> pd.Series:
    """2025 daily arrivals: each month's total spread by weekday weight, then scaled and shocked."""
    weights = pd.Series(
        _weekday_weights(code).loc[YEAR_DAYS.day_of_week].to_numpy(), index=YEAR_DAYS
    )
    month = YEAR_DAYS.strftime("%Y-%m")
    share = weights / weights.groupby(month).transform("sum")
    arrivals = share * month.map(monthly).to_numpy(float) * multiplier
    if shock != "none":
        spec = SHOCKS[shock]
        window = (YEAR_DAYS >= spec["start"]) & (YEAR_DAYS <= spec["end"])
        arrivals[window] *= spec["factors"].get(code, 1.0)
    return arrivals


def daily_capacity(code: str, crews_by_month: dict[str, float]) -> pd.Series:
    """Weekday capacity, scaled so each month adds up to the brief's crews x rate x 21 days."""
    weekday = YEAR_DAYS.day_of_week < 5
    month = YEAR_DAYS.strftime("%Y-%m")
    weekdays_in_month = pd.Series(weekday, index=YEAR_DAYS).groupby(month).transform("sum")
    per_crew = DEPARTMENTS[code]["requests_per_crew_day"] * WORK_DAYS_PER_MONTH
    monthly = month.map(crews_by_month).to_numpy(float) * per_crew
    return pd.Series(np.where(weekday, monthly / weekdays_in_month, 0.0), index=YEAR_DAYS)


def simulate(arrivals: pd.Series, capacity: pd.Series, sla: pd.DataFrame) -> pd.DataFrame:
    """Per arrival month: on-time-eligible requests, on-time requests, overdue cost, on-time rate.

    A request served on day s that arrived on day d with a k-day target is on time if s <= d + k.
    Requests still open on the last day count as late if their target has passed; ones not yet
    due are left out. Requests with no target use capacity but are not on-time-eligible.
    """
    shares = sla["share"].to_numpy(float) / sla["share"].sum()
    has_target = sla["target_days"].notna().to_numpy()
    targets, target_shares = sla["target_days"].to_numpy(float)[has_target], shares[has_target]
    eligible_share = target_shares.sum()
    delays = np.arange(len(arrivals) + 1)
    # share of a batch that is late, or 30+ days past target, when served `delay` days after arrival
    late = np.array([target_shares[targets < d].sum() for d in delays])
    late_30 = np.array([target_shares[targets + 30 <= d].sum() for d in delays])

    eligible, on_time, cost = (np.zeros(len(arrivals)) for _ in range(3))

    def score(day: int, delay: int, amount: float, served: bool) -> None:
        eligible[day] += amount * (eligible_share if served else late[delay])
        if served:
            on_time[day] += amount * (eligible_share - late[delay])
        cost[day] += amount * (
            OVERDUE_PENALTY * late[delay] + LATE_30_DAYS_PENALTY * late_30[delay]
        )

    queue = deque()  # [arrival day index, requests still open]
    days = zip(arrivals.to_numpy(), capacity.to_numpy(), strict=True)
    for today, (arrived, crews_left) in enumerate(days):
        if arrived > 0:
            queue.append([today, arrived])
        while crews_left > 0 and queue:
            day, still_open = queue[0]
            done = min(still_open, crews_left)
            score(day, today - day, done, served=True)
            crews_left -= done
            if done == still_open:
                queue.popleft()
            else:
                queue[0][1] -= done
    last = len(arrivals) - 1
    for day, still_open in queue:
        score(day, last - day, still_open, served=False)

    result = pd.DataFrame(
        {"eligible": eligible, "on_time": on_time, "overdue_cost": cost},
        index=arrivals.index.strftime("%Y-%m"),
    )
    result = result.groupby(level=0).sum()
    rate = result["on_time"] / result["eligible"].where(result["eligible"] > 0)
    result["on_time_pct"] = rate.fillna(1.0)
    return result
