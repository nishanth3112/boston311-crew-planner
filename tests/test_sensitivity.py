from types import SimpleNamespace

import pandas as pd
import pytest

from boston311.config import DEPARTMENTS
from boston311.planning import sensitivity
from boston311.planning.scenarios import SCENARIOS, load_plan


def test_scoring_a_plan_reproduces_its_own_kpis():
    # the sensitivity scorer and the planner use the same simulator, so they must agree
    for name in ["base", *sensitivity.SHOCK_SCENARIOS]:
        plan, request = load_plan(name), SCENARIOS[name]
        table = sensitivity.score(
            sensitivity.staffing(plan),
            dict.fromkeys(DEPARTMENTS, request.demand_multiplier),
            request.shock,
        )
        assert table.loc["all", "total_cost"] == pytest.approx(plan.kpis.total_cost, abs=1)
        assert table.loc["all", "on_time_pct"] == pytest.approx(plan.kpis.on_time_pct, abs=1e-4)


def test_the_all_row_adds_up_the_departments():
    table = sensitivity.score(
        sensitivity.staffing(load_plan("base")), dict.fromkeys(DEPARTMENTS, 1.0)
    )
    for column in ("crew_cost", "overdue_cost", "total_cost"):
        assert table.loc["all", column] == pytest.approx(table.loc[list(DEPARTMENTS), column].sum())


def test_held_fixed_against_replanned():
    table = sensitivity.held_vs_replanned()
    total = table[table["department"] == "all"].set_index(["scenario", "plan"])
    plus = total.loc["demand_plus_20"]
    # more demand on the same crews: on-time falls; re-planning hires to restore it
    assert plus.loc["held fixed", "on_time_pct"] < plus.loc["re-planned", "on_time_pct"]
    assert plus.loc["held fixed", "crew_cost"] < plus.loc["re-planned", "crew_cost"]
    minus = total.loc["demand_minus_20"]
    # less demand: re-planning releases crews and saves crew cost
    assert minus.loc["re-planned", "crew_cost"] < minus.loc["held fixed", "crew_cost"]
    # every held-fixed run uses the base plan's crews, so its crew cost never changes
    held = total.xs("held fixed", level="plan")["crew_cost"]
    assert held.round(2).nunique() == 1
    assert held.iloc[0] == pytest.approx(total.loc[("base", "base plan"), "crew_cost"])


def test_cost_curve_flags_departments_below_an_unreachable_target():
    curve = sensitivity.cost_curve([0.9, 0.98]).set_index("target")
    assert curve.loc[0.9, "departments_below_target"] == []
    assert curve.loc[0.98, "departments_below_target"] == ["PWDx", "BTDT"]
    assert curve.loc[0.98, "total_cost"] > curve.loc[0.9, "total_cost"]


def test_2025_ratios_and_replanning_for_them():
    ratios = sensitivity.actual_ratios()
    assert ratios == pytest.approx(
        {"PWDx": 0.844, "BTDT": 0.928, "PARK": 0.764, "ISD": 0.954}, abs=1e-3
    )
    table = sensitivity.actuals_2025().set_index(["plan", "department"])
    # with demand below forecast, a plan re-solved for it needs fewer crews
    assert (
        table.loc[("re-planned", "all"), "crew_cost"]
        < table.loc[("held fixed", "all"), "crew_cost"]
    )
    assert table.loc[("re-planned", "all"), "on_time_pct"] >= sensitivity.BASE_TARGET


def _days(values) -> pd.Series:
    # 2025-01-06 is a Monday
    return pd.Series(values, index=pd.date_range("2025-01-06", periods=len(values)), dtype=float)


def test_staffing_counts_seasonal_crews_and_adds_up_crew_cost():
    month = SimpleNamespace
    plan = SimpleNamespace(
        departments=[
            SimpleNamespace(
                department="PARK",
                months=[
                    month(month="2025-05", active_crews=10, seasonal=4, cost=100_000.0),
                    month(month="2025-06", active_crews=11, seasonal=6, cost=125_000.0),
                ],
            )
        ]
    )
    assert sensitivity.staffing(plan) == {
        "PARK": {"working": {"2025-05": 14, "2025-06": 17}, "crew_cost": 225_000.0}
    }


def test_score_on_a_toy_case_worked_out_by_hand(monkeypatch):
    # Monday to Wednesday, 10 requests each on Monday (times the multiplier), 1-day targets.
    # Only Public Works has crews (10 a day on Monday); every other department's requests are
    # still open on Wednesday, 1 day past target: $20 each, not yet the extra $100.
    calls = []

    def arrivals(code, monthly, multiplier, shock="none"):
        calls.append((code, multiplier, shock))
        return _days([10 * multiplier, 0, 0])

    monkeypatch.setattr(sensitivity, "_forecast", lambda: dict.fromkeys(DEPARTMENTS, {}))
    monkeypatch.setattr(sensitivity, "daily_arrivals", arrivals)
    monkeypatch.setattr(sensitivity, "daily_capacity", lambda code, w: _days([w["2025-01"], 0, 0]))
    monkeypatch.setattr(
        sensitivity, "sla_shares", lambda code: pd.DataFrame({"target_days": [1.0], "share": [1.0]})
    )
    staff = {code: {"working": {"2025-01": 0}, "crew_cost": 500.0} for code in DEPARTMENTS}
    staff["PWDx"] = {"working": {"2025-01": 10}, "crew_cost": 1_000.0}
    multipliers = {"PWDx": 1.0, "BTDT": 2.0, "PARK": 1.0, "ISD": 1.0}

    table = sensitivity.score(staff, multipliers, "snowstorm")

    assert calls == [(code, multipliers[code], "snowstorm") for code in DEPARTMENTS]
    expected = {
        # crew cost, overdue cost, total cost, on-time rate
        "PWDx": (1_000, 0, 1_000, 1.0),  # 10 served Monday, on time
        "BTDT": (500, 400, 900, 0.0),  # 20 late x $20
        "PARK": (500, 200, 700, 0.0),  # 10 late x $20
        "ISD": (500, 200, 700, 0.0),
        "all": (2_500, 800, 3_300, 0.2),  # 10 on time of 50
    }
    for row, values in expected.items():
        assert tuple(table.loc[row, sensitivity.COLUMNS]) == pytest.approx(values)
