import os

from fastapi import APIRouter

from boston311.api.schemas import (
    AskRequest,
    AskResponse,
    ForecastResult,
    HealthResponse,
    IntakeRequest,
    IntakeResponse,
    PlanResult,
    Scenario,
    SolveRequest,
)
from boston311.config import DEFAULT_LLM_MODEL
from boston311.forecast.models import load_forecast
from boston311.genai.analyst_agent import run_ask
from boston311.genai.intake_agent import run_intake
from boston311.planning.optimizer import solve_plan
from boston311.planning.scenarios import load_plan

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", model=os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL))


@router.post("/intake")
def intake(body: IntakeRequest) -> IntakeResponse:
    return run_intake(body.messages)


@router.get("/forecast")
def forecast() -> ForecastResult:
    return load_forecast()


@router.get("/plan")
def plan(scenario: Scenario = "base") -> PlanResult:
    return load_plan(scenario)


@router.post("/plan/solve")
def plan_solve(body: SolveRequest) -> PlanResult:
    return solve_plan(body)


@router.post("/ask")
def ask(body: AskRequest) -> AskResponse:
    return run_ask(body.messages)
