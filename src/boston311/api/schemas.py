"""The API contract. After changing it, regenerate openapi.json and web/src/api/schema.d.ts."""

from typing import Any, Literal

from pydantic import BaseModel, Field

Department = Literal["PWDx", "BTDT", "PARK", "ISD"]
Scenario = Literal[
    "base", "hold_flat", "demand_plus_20", "demand_minus_20", "snowstorm", "heat_wave"
]
Shock = Literal["none", "snowstorm", "heat_wave"]


class HealthResponse(BaseModel):
    status: str
    model: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    # caps keep one request inside Groq's free-tier token limits
    content: str = Field(min_length=1, max_length=4000)


class ToolTraceStep(BaseModel):
    tool: str
    args: dict[str, Any]
    summary: str


class IntakeRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


class RoutedRequest(BaseModel):
    request_type: str
    department: Department
    queue: str
    location: str | None
    details: str
    typical_days_to_close: float | None


class IntakeResponse(BaseModel):
    """Messages outside the four departments come back with out_of_scope=True and no requests."""

    requests: list[RoutedRequest]
    follow_up_question: str | None
    out_of_scope: bool
    reply: str
    trace: list[ToolTraceStep]
    fallback_used: bool = False


class ForecastMonth(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    forecast: float
    lower: float  # 80% interval
    upper: float


class DepartmentForecast(BaseModel):
    department: Department
    months: list[ForecastMonth]
    backtest_mape: float | None


class ForecastResult(BaseModel):
    departments: list[DepartmentForecast]


class PlanMonth(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    active_crews: int
    hires: int
    releases: int
    seasonal: int
    capacity: float
    forecast: float
    on_time_pct: float  # simulated, 0 to 1
    cost: float  # crew cost + release fees; overdue penalties are in kpis


class DepartmentPlan(BaseModel):
    department: Department
    months: list[PlanMonth]


class PlanKpis(BaseModel):
    """total_cost = crew cost + release fees + overdue penalties; overdue_cost is the penalty part.

    The baseline holds January crews flat all year.
    """

    total_cost: float
    overdue_cost: float
    on_time_pct: float
    baseline_total_cost: float
    baseline_overdue_cost: float
    baseline_on_time_pct: float


class PlanResult(BaseModel):
    scenario: str
    departments: list[DepartmentPlan]
    kpis: PlanKpis


class SolveRequest(BaseModel):
    demand_multiplier: float = Field(1.0, ge=0.5, le=1.5)
    shock: Shock = "none"
    on_time_target: float = Field(0.9, ge=0.5, le=0.99)


class AskRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


class AskResponse(BaseModel):
    answer: str
    trace: list[ToolTraceStep]
    what_if: SolveRequest | None
    unverified_numbers: list[str]
