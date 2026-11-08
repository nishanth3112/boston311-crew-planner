import time

import numpy as np
import pandas as pd
import pytest

from boston311.api.schemas import SolveRequest
from boston311.config import monthly_capacity
from boston311.forecast.models import load_forecast
from boston311.planning import optimizer
from boston311.planning.optimizer import hold_flat, solve_crews, solve_plan
from boston311.planning.scenarios import SCENARIOS, load_plan
from boston311.planning.simulator import daily_arrivals, daily_capacity, simulate

# 2025-01-04 is a Saturday and 2025-01-06 a Monday
ONE_DAY_TARGET = pd.DataFrame({"target_days": [1.0], "share": [1.0]})


def _days(values, start="2025-01-06") -> pd.Series:
    return pd.Series(values, index=pd.date_range(start, periods=len(values)), dtype=float)


def _totals(result: pd.DataFrame) -> dict:
    return result[["eligible", "on_time", "overdue_cost"]].sum().round(6).to_dict()


def test_weekday_arrivals_within_capacity_are_all_on_time():
    result = simulate(_days([10]), _days([10]), ONE_DAY_TARGET)
    assert _totals(result) == {"eligible": 10, "on_time": 10, "overdue_cost": 0}


def test_saturday_arrivals_wait_for_monday_and_are_late():
    # Sat, Sun, Mon: crews only on Monday, so a 1-day target is missed by a day
    result = simulate(
        _days([10, 0, 0], "2025-01-04"), _days([0, 0, 100], "2025-01-04"), ONE_DAY_TARGET
    )
    assert _totals(result) == {"eligible": 10, "on_time": 0, "overdue_cost": 200}


def test_requests_open_30_days_past_target_cost_the_extra_100():
    # no capacity for 46 days: on the last day the requests are 45 days old, 44 past target
    result = simulate(_days([10] + [0] * 45), _days([0] * 46), ONE_DAY_TARGET)
    assert _totals(result) == {"eligible": 10, "on_time": 0, "overdue_cost": 1_200}


@pytest.mark.parametrize(("days_open", "cost"), [(31, 1_200), (30, 200)])
def test_the_extra_100_starts_exactly_30_days_past_target(days_open, cost):
    # a 1-day target: open 31 days is exactly 30 past target, open 30 days is 29 past
    result = simulate(_days([10] + [0] * days_open), _days([0] * (days_open + 1)), ONE_DAY_TARGET)
    assert _totals(result)["overdue_cost"] == cost


def test_queue_is_first_in_first_out():
    # day 1 serves the 5 older requests only; the newer 5 are still open but not yet due
    result = simulate(_days([5, 5]), _days([0, 5]), ONE_DAY_TARGET)
    assert _totals(result) == {"eligible": 5, "on_time": 5, "overdue_cost": 0}


def test_past_due_requests_still_open_at_the_end_count_as_late():
    # 10 arrive Monday, 4 served Monday, 6 still open Wednesday: past their 1-day target
    result = simulate(_days([10, 0, 0]), _days([4, 0, 0]), ONE_DAY_TARGET)
    assert _totals(result) == {"eligible": 10, "on_time": 4, "overdue_cost": 120}


def test_requests_without_a_target_use_capacity_but_not_the_on_time_rate():
    sla = pd.DataFrame({"target_days": [1.0, np.nan], "share": [0.5, 0.5]})
    result = simulate(_days([10]), _days([10]), sla)
    assert _totals(result) == {"eligible": 5, "on_time": 5, "overdue_cost": 0}


def test_a_month_with_no_requests_reports_full_on_time():
    result = simulate(_days([0, 0]), _days([5, 5]), ONE_DAY_TARGET)
    assert result["on_time_pct"].tolist() == [1.0]
    assert _totals(result) == {"eligible": 0, "on_time": 0, "overdue_cost": 0}


def test_results_are_grouped_by_arrival_month():
    result = simulate(_days([4, 4], "2025-01-31"), _days([8, 0], "2025-01-31"), ONE_DAY_TARGET)
    assert result.index.tolist() == ["2025-01", "2025-02"]
    assert result["on_time"].tolist() == [4, 0]


def test_daily_capacity_adds_up_to_the_brief_monthly_capacity():
    crews = {f"2025-{m:02d}": 10 + m for m in range(1, 13)}
    capacity = daily_capacity("BTDT", crews)
    by_month = capacity.groupby(capacity.index.strftime("%Y-%m")).sum()
    for month, total in by_month.items():
        assert total == pytest.approx(monthly_capacity("BTDT", crews[month]))
    assert (capacity[capacity.index.day_of_week >= 5] == 0).all()


MONTHLY = {f"2025-{m:02d}": 1_000.0 * m for m in range(1, 13)}


def test_daily_arrivals_keep_monthly_totals_and_put_less_on_weekends():
    arrivals = daily_arrivals("PWDx", MONTHLY)
    by_month = arrivals.groupby(arrivals.index.strftime("%Y-%m")).sum()
    assert by_month.to_dict() == pytest.approx(MONTHLY)
    weekend = arrivals.index.day_of_week >= 5
    assert arrivals[weekend].mean() < 0.8 * arrivals[~weekend].mean()


def test_demand_multiplier_scales_every_day():
    assert daily_arrivals("ISD", MONTHLY, 1.2).sum() == pytest.approx(1.2 * sum(MONTHLY.values()))


def test_snowstorm_multiplies_only_its_window_and_departments():
    ratio = daily_arrivals("PWDx", MONTHLY, shock="snowstorm") / daily_arrivals("PWDx", MONTHLY)
    storm = (ratio.index >= "2025-02-03") & (ratio.index <= "2025-02-09")
    assert ratio[storm].to_numpy() == pytest.approx(3.0)
    assert ratio[~storm].to_numpy() == pytest.approx(1.0)
    parks = daily_arrivals("PARK", MONTHLY, shock="snowstorm") / daily_arrivals("PARK", MONTHLY)
    assert parks.to_numpy() == pytest.approx(1.0)


# MILP toy cases. ISD: 4 requests/crew/day -> 84 per crew per month, $11,666.67 per crew per
# month, $35,000 release fee. PARK: 6 -> 126 per crew per month, $10,000, seasonal $13,000.
ISD_MONTH = 140_000 / 12


def test_hire_in_month_one_works_from_month_two():
    plan = solve_crews("ISD", [168, 336, 168], next_jan=168, start_crews=2)
    assert plan["crews"] == [2, 4, 4]
    assert plan["hires"] == [2, 0, 0]
    # keeping 2 extra crews in month 3 ($23,333) beats a release fee ($70,000)
    assert plan["releases"] == [0, 0, 0]
    assert sum(plan["cost"]) == pytest.approx(12 * ISD_MONTH)  # $140,000


def test_release_pays_off_when_the_crews_are_idle_long_enough():
    plan = solve_crews("ISD", [168] * 6, next_jan=168, start_crews=6)
    assert plan["releases"] == [4, 0, 0, 0, 0, 0]
    assert plan["crews"] == [6, 2, 2, 2, 2, 2]
    assert sum(plan["cost"]) == pytest.approx(16 * ISD_MONTH + 4 * 35_000)  # $326,666.67


def test_december_crews_cover_the_january_need():
    # releasing all 4 extra crews and rehiring 2 in the last month beats keeping 2
    plan = solve_crews("ISD", [168] * 6, next_jan=336, start_crews=6)
    assert plan["releases"] == [4, 0, 0, 0, 0, 0]
    assert plan["hires"] == [0, 0, 0, 0, 0, 2]
    assert sum(plan["cost"]) == pytest.approx(18 * ISD_MONTH + 4 * 35_000)  # $350,000


def test_january_crews_are_fixed_even_when_short():
    plan = solve_crews("ISD", [1_000, 168], next_jan=168, start_crews=2)
    assert plan["crews"] == [2, 2]


def test_parks_covers_a_summer_peak_with_seasonal_crews():
    demand = [1_260] * 12
    demand[6] = 2_520  # July needs 10 more crews
    plan = solve_crews("PARK", demand, next_jan=1_260, start_crews=10)
    assert plan["seasonal"] == [0] * 6 + [10] + [0] * 5
    assert plan["hires"] == [0] * 12
    assert sum(plan["cost"]) == pytest.approx(12 * 10 * 10_000 + 10 * 13_000)  # $1,330,000


def test_seasonal_crews_are_only_used_april_to_october():
    demand = [1_260] * 12
    demand[11] = 2_520  # a December peak must be met with permanent crews
    plan = solve_crews("PARK", demand, next_jan=1_260, start_crews=10)
    assert plan["seasonal"] == [0] * 12
    assert plan["hires"][10] == 10


def test_buffer_raises_capacity_above_demand():
    plan = solve_crews("ISD", [168, 168], next_jan=168, start_crews=2, buffer=0.5)
    assert plan["crews"] == [2, 3]  # 1.5 x 168 = 252 = 3 crews


def test_other_departments_never_get_seasonal_crews():
    plan = solve_crews("ISD", [168] * 7 + [840] * 5, next_jan=168, start_crews=2)
    assert plan["seasonal"] == [0] * 12


@pytest.mark.parametrize(
    ("demand", "next_jan", "start"), [([-1, 10], 10, 2), ([10, 10], -1, 2), ([10, 10], 10, -1)]
)
def test_negative_inputs_are_rejected(demand, next_jan, start):
    with pytest.raises(ValueError):
        solve_crews("ISD", demand, next_jan=next_jan, start_crews=start)


def test_hold_flat_keeps_january_crews_all_year():
    plan = hold_flat("BTDT", 12)
    assert plan["crews"] == [18] * 12
    assert plan["hires"] == plan["releases"] == plan["seasonal"] == [0] * 12
    assert sum(plan["cost"]) == pytest.approx(18 * 110_000)


def test_base_plan_solves_in_under_5_seconds_and_beats_holding_crews_flat():
    start = time.perf_counter()
    plan = solve_plan(SolveRequest())
    assert time.perf_counter() - start < 5
    assert [d.department for d in plan.departments] == ["PWDx", "BTDT", "PARK", "ISD"]
    assert all(len(d.months) == 12 for d in plan.departments)
    k = plan.kpis
    assert k.on_time_pct >= 0.9 > k.baseline_on_time_pct
    assert k.total_cost < k.baseline_total_cost


def test_committed_plans_match_a_fresh_solve():
    # KPIs, not the whole plan: CBC on another platform may pick a different equal-cost plan
    fresh = solve_plan(SolveRequest()).kpis.model_dump()
    committed = load_plan("base").kpis.model_dump()
    assert committed == pytest.approx(fresh, rel=1e-6), "run: uv run python scripts/build_plans.py"


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_named_plan_loads(name):
    assert load_plan(name).scenario == name


def test_hold_flat_plan_is_the_baseline():
    plan = load_plan("hold_flat")
    months = [m for d in plan.departments for m in d.months]
    assert all(m.hires == m.releases == m.seasonal == 0 for m in months)
    k = plan.kpis
    assert (k.total_cost, k.overdue_cost, k.on_time_pct) == (
        k.baseline_total_cost,
        k.baseline_overdue_cost,
        k.baseline_on_time_pct,
    )


def test_a_one_week_shock_does_not_staff_the_whole_year():
    def june_crews(request):
        return {d.department: d.months[5].active_crews for d in solve_plan(request).departments}

    assert june_crews(SolveRequest(shock="snowstorm")) == june_crews(SolveRequest())


def test_an_unreachable_target_stops_at_the_buffer_cap_with_the_best_plan():
    # Transportation tops out near 95%: weekday crews can't meet Saturday's 1-day targets
    monthly = {m.month: m.forecast for m in load_forecast(["BTDT"]).departments[0].months}
    arrivals = daily_arrivals("BTDT", monthly)

    def on_time(target):
        _, sim = optimizer.plan_department("BTDT", arrivals, monthly["2025-01"], target)
        return sim["on_time"].sum() / sim["eligible"].sum()

    assert on_time(0.9) < on_time(0.99) < 0.99


def test_buffer_loop_returns_the_plan_that_meets_the_target(monkeypatch):
    # 89.96% and 90.03% both round to 90.0%; the second one meets a 90% target
    rates = iter([0.8996, 0.9003])

    def fake_score(code, plan, arrivals, sla):
        rate = next(rates)
        return pd.DataFrame(
            {"eligible": [1.0] * 12, "on_time": [rate] * 12, "on_time_pct": [rate] * 12}
        )

    monkeypatch.setattr(optimizer, "_score", fake_score)
    _, sim = optimizer.plan_department("ISD", daily_arrivals("ISD", MONTHLY), 1_000, 0.9)
    assert sim["on_time"].sum() / sim["eligible"].sum() == pytest.approx(0.9003)
