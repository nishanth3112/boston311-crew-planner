from boston311.api.fixtures import load_fixture
from boston311.api.schemas import PlanResult, Scenario


def load_plan(scenario: Scenario = "base") -> PlanResult:
    """Return a precomputed named plan."""
    # stub: BOS-7 replaces this body
    return load_fixture("plan", PlanResult).model_copy(update={"scenario": scenario})
