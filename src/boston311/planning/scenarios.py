"""Named plans, precomputed by scripts/build_plans.py so /api/plan answers instantly."""

import json

from boston311.api.schemas import PlanResult, Scenario, SolveRequest
from boston311.config import PROCESSED_DIR
from boston311.planning.optimizer import solve_plan

PLANS_PATH = PROCESSED_DIR / "plans.json"

# every scenario is re-optimized for its demand; hold_flat is the baseline itself
SCENARIOS: dict[Scenario, SolveRequest] = {
    "base": SolveRequest(),
    "hold_flat": SolveRequest(),
    "demand_plus_20": SolveRequest(demand_multiplier=1.2),
    "demand_minus_20": SolveRequest(demand_multiplier=0.8),
    "snowstorm": SolveRequest(shock="snowstorm"),
    "heat_wave": SolveRequest(shock="heat_wave"),
}


def build_plans() -> dict[str, PlanResult]:
    return {
        name: solve_plan(request, flat=name == "hold_flat").model_copy(update={"scenario": name})
        for name, request in SCENARIOS.items()
    }


def load_plan(scenario: Scenario = "base") -> PlanResult:
    """Return a precomputed named plan."""
    return PlanResult.model_validate(json.loads(PLANS_PATH.read_text())[scenario])
