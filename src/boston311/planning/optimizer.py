from boston311.api.fixtures import load_fixture
from boston311.api.schemas import PlanResult, SolveRequest


def solve_plan(request: SolveRequest) -> PlanResult:
    """Solve the MILP for these settings and score it with the daily simulator."""
    # stub: BOS-7 replaces this body
    return load_fixture("plan", PlanResult).model_copy(update={"scenario": "custom"})
