from boston311.api.fixtures import load_fixture
from boston311.api.schemas import Department, ForecastResult


def load_forecast(departments: list[Department] | None = None) -> ForecastResult:
    """Monthly 2025 forecast with 80% interval; all four departments when None."""
    # stub: BOS-5 replaces this body
    result = load_fixture("forecast", ForecastResult)
    if departments:
        result.departments = [d for d in result.departments if d.department in departments]
    return result
