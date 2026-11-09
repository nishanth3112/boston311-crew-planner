"""Sensitivity: how the 2025 plan holds up when demand differs from the forecast.

Every view is scored by the same daily simulator as the plan itself:
- held fixed vs re-planned: each named scenario's demand run against the base plan's crews,
  and against the plan re-solved for that demand;
- the cost of each on-time target (the cost versus on-time curve);
- 2025 as it happened: each department's demand at its January-September 2025 ratio of actual
  to forecast requests, applied to the whole year.
"""

import pandas as pd

from boston311.api.schemas import PlanResult, SolveRequest
from boston311.config import DEPARTMENTS
from boston311.forecast import backtest
from boston311.forecast.models import FORECAST_PATH, load_forecast
from boston311.planning.optimizer import plan_department, solve_plan
from boston311.planning.scenarios import SCENARIOS, load_plan
from boston311.planning.simulator import daily_arrivals, daily_capacity, simulate, sla_shares

SHOCK_SCENARIOS = ["demand_plus_20", "demand_minus_20", "snowstorm", "heat_wave"]
TARGETS = [round(0.80 + 0.02 * i, 2) for i in range(10)]  # 0.80 to 0.98
BASE_TARGET = SCENARIOS["base"].on_time_target
COLUMNS = ["crew_cost", "overdue_cost", "total_cost", "on_time_pct"]


def _forecast() -> dict[str, dict[str, float]]:
    return {
        d.department: {m.month: m.forecast for m in d.months} for d in load_forecast().departments
    }


def staffing(plan: PlanResult) -> dict[str, dict]:
    """Per department: working crews (regular + seasonal) by month, and crew cost for the
    year (crews, hires in training and release fees)."""
    return {
        d.department: {
            "working": {m.month: m.active_crews + m.seasonal for m in d.months},
            "crew_cost": sum(m.cost for m in d.months),
        }
        for d in plan.departments
    }


def score(staff: dict, multipliers: dict[str, float], shock: str = "none") -> pd.DataFrame:
    """Simulate each department's demand (forecast x its multiplier, plus the shock) against
    fixed staffing. One row per department and one for "all": crew cost, overdue cost, total
    cost and on-time rate (requests with no target date left out, as in the plan)."""
    forecast = _forecast()
    rows = []
    for code in DEPARTMENTS:
        arrivals = daily_arrivals(code, forecast[code], multipliers[code], shock)
        sim = simulate(arrivals, daily_capacity(code, staff[code]["working"]), sla_shares(code))
        rows.append(
            {
                "department": code,
                "crew_cost": staff[code]["crew_cost"],
                "overdue_cost": sim["overdue_cost"].sum(),
                "on_time": sim["on_time"].sum(),
                "eligible": sim["eligible"].sum(),
            }
        )
    table = pd.DataFrame(rows).set_index("department")
    table.loc["all"] = table.sum()
    table["total_cost"] = table["crew_cost"] + table["overdue_cost"]
    table["on_time_pct"] = table["on_time"] / table["eligible"]
    return table[COLUMNS]


def _same(multiplier: float) -> dict[str, float]:
    return dict.fromkeys(DEPARTMENTS, multiplier)


def held_vs_replanned() -> pd.DataFrame:
    """The base plan, then for each shock scenario the base plan's crews held fixed under it
    and the plan re-solved for it. Columns: scenario, plan, department and COLUMNS."""
    base = staffing(load_plan("base"))
    frames = [score(base, _same(1.0)).assign(scenario="base", plan="base plan")]
    for name in SHOCK_SCENARIOS:
        request = SCENARIOS[name]
        demand = _same(request.demand_multiplier)
        replanned = staffing(load_plan(name))
        for plan, staff in (("held fixed", base), ("re-planned", replanned)):
            frames.append(score(staff, demand, request.shock).assign(scenario=name, plan=plan))
    return pd.concat(frames).reset_index()[["scenario", "plan", "department", *COLUMNS]]


def cost_curve(targets: list[float] = TARGETS) -> pd.DataFrame:
    """The plan re-solved for each on-time target: total cost, simulated on-time rate, and the
    departments whose own rate falls short (the planner keeps its best plan when a target is
    out of reach)."""
    rows = []
    for target in targets:
        table = score(staffing(solve_plan(SolveRequest(on_time_target=target))), _same(1.0))
        rows.append(
            {
                "target": target,
                "total_cost": table.loc["all", "total_cost"],
                "on_time_pct": table.loc["all", "on_time_pct"],
                "departments_below_target": [
                    code for code in DEPARTMENTS if table.loc[code, "on_time_pct"] < target
                ],
            }
        )
    return pd.DataFrame(rows)


def actual_ratios() -> dict[str, float]:
    """Each department's January-September 2025 actual requests over its forecast."""
    series = backtest.monthly_series()
    check = backtest.check_2025(series, pd.read_parquet(FORECAST_PATH))
    return dict(zip(check["department"], check["actual_vs_forecast"], strict=True))


def actuals_2025() -> pd.DataFrame:
    """Demand at each department's 2025 actual/forecast ratio for the whole year: the base plan
    held fixed against it, and a plan re-solved for it at the base target."""
    ratios = actual_ratios()
    forecast = _forecast()
    replanned = {}
    for code in DEPARTMENTS:
        arrivals = daily_arrivals(code, forecast[code], ratios[code])
        next_jan = forecast[code]["2025-01"] * ratios[code]
        plan, _ = plan_department(code, arrivals, next_jan, BASE_TARGET)
        months = sorted(forecast[code])
        working = [c + s for c, s in zip(plan["crews"], plan["seasonal"], strict=True)]
        replanned[code] = {
            "working": dict(zip(months, working, strict=True)),
            "crew_cost": sum(plan["cost"]),
        }
    held = score(staffing(load_plan("base")), ratios).assign(plan="held fixed")
    return pd.concat([held, score(replanned, ratios).assign(plan="re-planned")]).reset_index()[
        ["plan", "department", *COLUMNS]
    ]
