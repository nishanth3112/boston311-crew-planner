import json

import groq
import httpx
import pytest
from fastapi.testclient import TestClient

from boston311.api import main, routes, schemas
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


@pytest.fixture
def web_dist(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>')
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("SECRET")  # next to the build, one level up
    monkeypatch.setattr(main, "DIST", dist)
    return dist


@pytest.mark.parametrize("path", ["/", "/plan", "/scenarios", "/ask"])
def test_app_routes_get_the_web_app(web_dist, path):
    response = client.get(path)
    assert response.status_code == 200 and '<div id="root">' in response.text


def test_built_files_are_served_as_they_are(web_dist):
    assert client.get("/assets/app.js").text == "console.log(1)"


def test_unknown_api_paths_stay_404(web_dist):
    assert client.get("/api/nope").status_code == 404


@pytest.mark.parametrize("path", ["/..%2fsecret.txt", "/assets/..%2f..%2fsecret.txt"])
def test_paths_outside_the_build_are_never_served(web_dist, path):
    # secret.txt really exists at these paths, so without the guard it would be served
    response = client.get(path)
    assert "SECRET" not in response.text and '<div id="root">' in response.text


def test_an_absolute_path_is_never_served(web_dist):
    # "/%2f..." reaches the route as an absolute path, and root / "/x" is just "/x"
    secret = web_dist.parent / "secret.txt"
    response = client.get("/%2f" + str(secret).lstrip("/"))
    assert "SECRET" not in response.text and '<div id="root">' in response.text


@pytest.mark.parametrize("path", ["/%00", "/assets/%00x", "/plan%00.html"])
def test_a_null_byte_in_the_path_is_404_not_500(web_dist, path):
    assert client.get(path).status_code == 404


def test_without_a_build_the_app_route_is_404(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DIST", tmp_path)
    assert client.get("/plan").status_code == 404


BUSY = "The assistant is busy right now. Try again in a minute."
UNAVAILABLE = "The assistant isn't available right now."


def _groq_status(cls, code):
    request = httpx.Request("POST", "https://api.groq.com")
    return cls("groq", response=httpx.Response(code, request=request), body=None)


@pytest.mark.parametrize("path", ["/api/intake", "/api/ask"])
@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (_groq_status(groq.RateLimitError, 429), BUSY),
        (_groq_status(groq.AuthenticationError, 401), UNAVAILABLE),
        (groq.GroqError("The api_key client option must be set"), UNAVAILABLE),
    ],
)
def test_groq_errors_return_friendly_503(path, error, detail, monkeypatch):
    def fail(messages):
        raise error

    monkeypatch.setattr(routes, "run_intake", fail)
    monkeypatch.setattr(routes, "run_ask", fail)
    response = client.post(path, json=MESSAGES)
    assert response.status_code == 503
    assert response.json() == {"detail": detail}
