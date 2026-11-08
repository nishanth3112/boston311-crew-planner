import json

import pytest
from fastapi.testclient import TestClient

from boston311.api import routes, schemas
from boston311.api.fixtures import load_fixture
from boston311.api.main import app
from boston311.config import ROOT

client = TestClient(app)
MESSAGES = {"messages": [{"role": "user", "content": "Trash wasn't picked up on Adams St"}]}


@pytest.mark.parametrize(
    ("method", "path", "body", "model"),
    [
        ("get", "/api/health", None, schemas.HealthResponse),
        ("post", "/api/intake", MESSAGES, schemas.IntakeResponse),
        ("get", "/api/forecast", None, schemas.ForecastResult),
        ("get", "/api/plan?scenario=base", None, schemas.PlanResult),
        ("post", "/api/plan/solve", {"demand_multiplier": 1.2}, schemas.PlanResult),
        ("post", "/api/ask", MESSAGES, schemas.AskResponse),
    ],
)
def test_route_returns_valid_response(method, path, body, model, monkeypatch):
    # the real intake and analyst agents call Groq; this test checks the route's shape, so CI
    # needs no key
    fixture = load_fixture("intake", schemas.IntakeResponse)
    monkeypatch.setattr(routes, "run_intake", lambda messages: fixture)
    ask_fixture = load_fixture("ask", schemas.AskResponse)
    monkeypatch.setattr(routes, "run_ask", lambda messages: ask_fixture)
    response = client.request(method, path, json=body)
    assert response.status_code == 200
    model.model_validate(response.json())


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/plan/solve", {"demand_multiplier": 2.0}),
        ("/api/plan/solve", {"on_time_target": 1.0}),
        ("/api/plan/solve", {"shock": "flood"}),
        ("/api/intake", {"messages": []}),
        ("/api/ask", {"messages": [{"role": "system", "content": "x"}]}),
        ("/api/intake", {"messages": [{"role": "user", "content": ""}]}),
        ("/api/intake", {"messages": [{"role": "user", "content": "x" * 4001}]}),
        ("/api/ask", {"messages": [{"role": "user", "content": "x"}] * 21}),
    ],
)
def test_invalid_input_is_rejected(path, body):
    assert client.post(path, json=body).status_code == 422


def test_unknown_scenario_is_rejected():
    assert client.get("/api/plan?scenario=nope").status_code == 422


def test_health_falls_back_to_default_model(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert client.get("/api/health").json()["model"] == "openai/gpt-oss-20b"


def test_committed_openapi_matches_app():
    committed = json.loads((ROOT / "openapi.json").read_text())
    assert committed == app.openapi(), "run: uv run python scripts/export_openapi.py"
