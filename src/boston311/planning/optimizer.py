"""Monthly crew MILP per department, the buffer loop that tunes it with the simulator, and the
plan the API serves."""

import pulp

from boston311.api.schemas import DepartmentPlan, PlanKpis, PlanMonth, PlanResult, SolveRequest
from boston311.config import (
    DEPARTMENTS,
    RELEASE_FEE_SHARE,
    SEASONAL_COST_MULTIPLIER,
    SEASONAL_DEPT,
    SEASONAL_MONTHS,
    WORK_DAYS_PER_MONTH,
    monthly_capacity,
    monthly_crew_cost,
)
from boston311.forecast.models import load_forecast
from boston311.planning.simulator import daily_arrivals, daily_capacity, simulate, sla_shares

BUFFER_STEP, MAX_BUFFER = 0.02, 0.5  # extra capacity over demand, raised month by month


def solve_crews(
    code: str,
    demand: list[float],
    next_jan: float,
    start_crews: int,
    buffer: float | list[float] = 0.0,
) -> dict[str, list]:
    """Cheapest crews, hires, releases and seasonal crews for months starting in January.

    Timing (working assumption 2): a hire is paid in t and works from t+1; a release works t,
    is gone from t+1, and its fee is charged in t. January crews are given, so capacity is
    required from February on. The crews left after the last month must cover next_jan, with
    the last month's buffer. buffer is one value for every month, or one per month.
    """
    if min(demand) < 0 or next_jan < 0 or start_crews < 0:
        raise ValueError("demand, next_jan and start_crews must not be negative")
    dept = DEPARTMENTS[code]
    per_crew = dept["requests_per_crew_day"] * WORK_DAYS_PER_MONTH
    month_cost = monthly_crew_cost(code)
    fee = RELEASE_FEE_SHARE * dept["annual_cost"]
    months = range(len(demand))
    buffers = buffer if isinstance(buffer, list) else [buffer] * len(demand)
    model = pulp.LpProblem(code, pulp.LpMinimize)

    def ints(name, upper=None):
        return [
            model.add_variable(f"{name}_{t}", 0, upper(t) if upper else None, "Integer")
            for t in months
        ]

    crews, hires, releases = ints("crews"), ints("hires"), ints("releases")
    seasonal = ints(
        "seasonal", lambda t: None if code == SEASONAL_DEPT and t + 1 in SEASONAL_MONTHS else 0
    )

    model += pulp.lpSum(
        month_cost * (crews[t] + hires[t] + SEASONAL_COST_MULTIPLIER * seasonal[t])
        + fee * releases[t]
        for t in months
    )
    model += crews[0] == start_crews
    for t in months:
        if t + 1 < len(demand):
            model += crews[t + 1] == crews[t] + hires[t] - releases[t]
        if t > 0:
            model += (crews[t] + seasonal[t]) * per_crew >= (1 + buffers[t]) * demand[t]
    last = months[-1]
    model += (crews[last] + hires[last] - releases[last]) * per_crew >= (1 + buffers[-1]) * next_jan

    status = model.solve(pulp.COIN_CMD(msg=False, gapRel=0)).status
    # PuLP 4 reports CBC's "optimal (within gap tolerance)" as GapLimit; the gap asked is 0
    if status not in (pulp.LpSolveStatus.Optimal, pulp.LpSolveStatus.GapLimit):
        raise RuntimeError(f"{code} crew plan is {status.name}")
    plan = {
        name: [round(v.value()) for v in variables]
        for name, variables in [
            ("crews", crews),
            ("hires", hires),
            ("releases", releases),
            ("seasonal", seasonal),
        ]
    }
    plan["cost"] = [
        month_cost * (c + h + SEASONAL_COST_MULTIPLIER * s) + fee * r
        for c, h, r, s in zip(
            plan["crews"], plan["hires"], plan["releases"], plan["seasonal"], strict=True
        )
    ]
    return plan


def hold_flat(code: str, months: int) -> dict[str, list]:
    """The baseline: January crews all year, no hires, releases or seasonal crews."""
    crews = DEPARTMENTS[code]["jan_crews"]
    zeros = [0] * months
    return {
        "crews": [crews] * months,
        "hires": zeros,
        "releases": zeros,
        "seasonal": zeros,
        "cost": [crews * monthly_crew_cost(code)] * months,
    }


def _on_time(sim) -> float:
    return sim["on_time"].sum() / sim["eligible"].sum() if sim["eligible"].sum() else 1.0


def _score(code, plan, arrivals, sla):
    working = [c + s for c, s in zip(plan["crews"], plan["seasonal"], strict=True)]
    months = sorted(set(arrivals.index.strftime("%Y-%m")))
    return simulate(arrivals, daily_capacity(code, dict(zip(months, working, strict=True))), sla)


def plan_department(code, arrivals, next_jan, target):
    """Raise buffers until the department's simulated on-time rate for the year reaches the target.

    Each round adds a step only to the months (February on) that are below the target, so a
    one-week shock or the fixed January crews don't overstaff the whole year. If the target
    can't be reached with buffers up to 50%, keep the best rate seen (the cheapest on ties).
    """
    monthly = arrivals.groupby(arrivals.index.strftime("%Y-%m")).sum().tolist()
    sla = sla_shares(code)
    buffers = [0.0] * len(monthly)
    best = None
    while True:
        plan = solve_crews(code, monthly, next_jan, DEPARTMENTS[code]["jan_crews"], buffers)
        sim = _score(code, plan, arrivals, sla)
        if _on_time(sim) >= target:
            return plan, sim
        # gains under 0.1 points don't justify a costlier plan
        if best is None or round(_on_time(sim), 3) > round(_on_time(best[1]), 3):
            best = plan, sim
        late = [
            t
            for t in range(1, len(monthly))
            if sim["on_time_pct"].iloc[t] < target and buffers[t] < MAX_BUFFER
        ]
        if not late:
            return best
        for t in late:
            buffers[t] += BUFFER_STEP


def _flat_department(code, arrivals, next_jan, target):
    plan = hold_flat(code, 12)
    return plan, _score(code, plan, arrivals, sla_shares(code))


def _department_plan(code, plan, sim, arrivals) -> DepartmentPlan:
    demand = arrivals.groupby(arrivals.index.strftime("%Y-%m")).sum()
    months = [
        PlanMonth(
            month=month,
            active_crews=plan["crews"][i],
            hires=plan["hires"][i],
            releases=plan["releases"][i],
            seasonal=plan["seasonal"][i],
            capacity=monthly_capacity(code, plan["crews"][i] + plan["seasonal"][i]),
            forecast=round(demand[month], 1),
            on_time_pct=round(sim.loc[month, "on_time_pct"], 4),
            cost=round(plan["cost"][i], 2),
        )
        for i, month in enumerate(demand.index)
    ]
    return DepartmentPlan(department=code, months=months)


def solve_plan(request: SolveRequest, flat: bool = False) -> PlanResult:
    """Solve and simulate every department, and compare with holding January crews flat.

    flat=True returns the hold-flat baseline itself as the plan. The on-time target is not
    guaranteed: a department that can't reach it with buffers up to 50% keeps its best rate,
    so compare kpis.on_time_pct with request.on_time_target to see whether it was met.
    """
    forecast = {
        d.department: {m.month: m.forecast for m in d.months} for d in load_forecast().departments
    }
    planner = _flat_department if flat else plan_department
    departments, planned, baseline = [], [], []  # (plan, sim) per department
    for code in DEPARTMENTS:
        arrivals = daily_arrivals(code, forecast[code], request.demand_multiplier, request.shock)
        next_jan = forecast[code]["2025-01"] * request.demand_multiplier
        plan, sim = planner(code, arrivals, next_jan, request.on_time_target)
        planned.append((plan, sim))
        baseline.append(_flat_department(code, arrivals, next_jan, request.on_time_target))
        departments.append(_department_plan(code, plan, sim, arrivals))

    def kpis(results):
        crew = sum(sum(plan["cost"]) for plan, _ in results)
        overdue = sum(sim["overdue_cost"].sum() for _, sim in results)
        on_time = sum(sim["on_time"].sum() for _, sim in results)
        eligible = sum(sim["eligible"].sum() for _, sim in results)
        return round(crew + overdue, 2), round(overdue, 2), round(on_time / eligible, 4)

    (total, overdue, on_time), (b_total, b_overdue, b_on_time) = kpis(planned), kpis(baseline)
    return PlanResult(
        scenario="custom",
        departments=departments,
        kpis=PlanKpis(
            total_cost=total,
            overdue_cost=overdue,
            on_time_pct=on_time,
            baseline_total_cost=b_total,
            baseline_overdue_cost=b_overdue,
            baseline_on_time_pct=b_on_time,
        ),
    )
