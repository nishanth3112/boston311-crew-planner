import json
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest
from groq import BadRequestError
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from boston311.api.schemas import AskResponse, ChatMessage, ToolTraceStep
from boston311.eval import analyst_eval
from boston311.eval.analyst_eval import load_set, score
from boston311.genai import analyst_agent, llm
from boston311.genai.analyst_agent import known_values, unverified_numbers


def ask(text: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=text)]


# ---------- number check ----------


def known(*results, question=""):
    return known_values([json.dumps(r) for r in results], [question])


def test_rates_written_as_percentages_of_fractions_are_verified():
    k = known({"on_time_pct": 0.9206})
    assert unverified_numbers("The plan closes 92.1% on time, or 92% overall.", k) == []
    assert unverified_numbers("It closes 92.6% on time.", k) == ["92.6%"]


def test_money_in_millions_and_thousands_rounds_to_the_precision_written():
    k = known({"total_cost": 15909155.15, "cost": 2860000})
    answer = "It costs $15.91M, about $16 million, or $15,909,155; Transportation $2,860 thousand."
    assert unverified_numbers(answer, k) == []
    assert unverified_numbers("It costs $15.95M.", k) == ["$15.95M"]


def test_round_numbers_are_precise_to_their_last_nonzero_digit():
    k = known({"total_2025": 88079})
    assert unverified_numbers("About 88,000 requests, or 88,079 exactly.", k) == []
    assert unverified_numbers("About 89,000 requests.", k) == ["89,000"]


def test_years_are_skipped_and_numbers_from_the_question_count():
    k = known({"hires": 9}, question="What if demand is 20% higher in 2025?")
    answer = "With demand 20% higher in 2025, Transportation hires 9 crews, up from 2024."
    assert unverified_numbers(answer, k) == []


def test_numbers_the_model_computes_itself_are_flagged_once():
    k = known({"cost_a": 100, "cost_b": 40})
    answer = "A costs 100 and B costs 40, so A costs 60 more. Again: 60."
    assert unverified_numbers(answer, k) == ["60"]


def test_negative_changes_match_by_size():
    k = known({"change_from_base": {"on_time_pct": -0.0145}})
    assert unverified_numbers("On-time falls by 1.45 points (1.4%).", k) == []
    assert unverified_numbers("On-time falls by 1.6%.", k) == ["1.6%"]


# ---------- tools ----------


def load(tool, **args):
    return json.loads(tool.invoke(args))


def test_get_forecast_returns_method_interval_and_2024_comparison():
    (btdt,) = load(analyst_agent.get_forecast, departments=["BTDT"])
    assert btdt["method"] == "naive_yoy"
    assert len(btdt["forecast"]) == 12
    assert all(
        lo <= f <= hi
        for lo, f, hi in zip(btdt["lower"], btdt["forecast"], btdt["upper"], strict=True)
    )
    assert btdt["total_2024"] == 81447
    assert btdt["change_vs_2024"] == pytest.approx(btdt["total_2025"] / 81447 - 1, abs=1e-4)


def test_service_stats_clamps_the_limit_and_adds_shares():
    out = load(
        analyst_agent.query_service_stats, metric="request_count", group_by="source", limit=999
    )
    rows = out["results"][0]["rows"]
    assert out["results"][0]["department"] == "all"
    assert len(rows) <= analyst_agent.MAX_ROWS
    assert sum(r["share"] for r in rows) == pytest.approx(1, abs=0.01)


def test_service_stats_rejects_years_without_data_and_suggests_names():
    assert "error" in load(
        analyst_agent.query_service_stats, metric="on_time_rate", group_by="month", year=2019
    )
    out = load(
        analyst_agent.query_service_stats,
        metric="on_time_rate",
        group_by="neighborhood",
        request_type="Pothole repair",
    )
    assert "Request for Pothole Repair" in out["results"][0]["closest_names"]["request_type"]


def test_service_stats_runs_once_per_department():
    out = load(
        analyst_agent.query_service_stats,
        metric="on_time_rate",
        group_by="department",
        departments=["PWDx", "ISD"],
    )
    assert [r["department"] for r in out["results"]] == ["PWDx", "ISD"]
    assert out["results"][0]["rows"] == [{"department": "PWDx", "on_time_rate": 0.873}]


def test_get_plan_filters_departments_and_totals_them():
    out = load(analyst_agent.get_plan, scenario="base", departments=["PARK"])
    (park,) = out["departments"]
    assert park["totals"]["hires"] == sum(park["hires"])
    assert park["totals"]["seasonal_crew_months"] == sum(park["seasonal"])
    assert set(out["all_departments"]) >= {"total_cost", "on_time_pct", "baseline_on_time_pct"}


def test_what_if_with_base_settings_shows_no_change():
    out = load(analyst_agent.run_what_if, departments=["ISD"])
    assert out["target_met"] is True
    assert out["all_departments"]["change_from_base"] == {
        "total_cost": 0,
        "overdue_cost": 0,
        "on_time_pct": 0,
    }
    assert set(out["departments"][0]["change_from_base"].values()) == {0}


def test_what_if_reports_an_unreachable_target_and_bad_input():
    out = load(analyst_agent.run_what_if, on_time_target=0.99, departments=["BTDT"])
    assert out["target_met"] is False and out["all_departments"]["on_time_pct"] < 0.99
    assert load(analyst_agent.run_what_if, demand_multiplier=3) == {
        "error": "demand_multiplier: Input should be less than or equal to 1.5"
    }


# ---------- the agent, with a scripted model ----------


class FakeToolModel(GenericFakeChatModel):
    """Scripted chat model that accepts tools, for driving create_agent offline."""

    def bind_tools(self, tools, **kwargs):
        return self


def call(name, i, **args):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{i}"}])


@pytest.fixture
def script(monkeypatch):
    def use(*messages, model_class=FakeToolModel):
        model = model_class(messages=iter(messages))
        monkeypatch.setattr(llm, "chat_model", lambda model_name=None: model)
        return model

    return use


def test_agent_answers_from_tools_and_flags_its_own_arithmetic(script):
    script(
        call("get_plan", 1, scenario="base", departments=["BTDT"]),
        call("run_what_if", 2, demand_multiplier=1.2, departments=["BTDT"]),
        AIMessage("With demand 20% higher Transportation hires 777 crews, 10 more than 9."),
    )
    response, stats = analyst_agent.run_ask_with_stats(
        ask("What happens to Transportation if demand is 20% higher?")
    )
    assert [s.summary for s in response.trace] == [
        "Read the base plan for Transportation",
        "Re-ran the plan with demand +20%",
    ]
    assert response.what_if.demand_multiplier == 1.2 and response.what_if.shock == "none"
    # 9 is the base plan's hires and 10 the change run_what_if returned; 777 is made up
    assert response.unverified_numbers == ["777"]
    assert (stats["tool_calls"], stats["numbers"], stats["unverified"]) == (2, 4, 1)


def test_answer_without_a_what_if_has_no_scenario_link(script):
    script(
        call("get_forecast", 1, departments=["ISD"]),
        AIMessage("Inspectional Services expects 18,624 requests in 2025."),
    )
    response = analyst_agent.run_ask(ask("How many ISD requests in 2025?"))
    assert response.what_if is None and response.unverified_numbers == []
    assert response.trace[0].summary == "Read the 2025 forecast for Inspectional Services"


def test_tool_call_cap_ends_with_a_clear_message(script):
    script(*[call("get_forecast", i, departments=["ISD"]) for i in range(10)])
    response, stats = analyst_agent.run_ask_with_stats(ask("Forecast?"))
    assert response.answer.startswith("I couldn't finish within 6 tool calls")
    assert response.unverified_numbers == []  # the 6 comes from the server, not the model
    assert stats["tool_calls"] == len(response.trace) == analyst_agent.MAX_TOOL_CALLS


class FlakyToolModel(FakeToolModel):
    """Fails its first call the way Groq rejects a misnamed tool call."""

    failed: bool = False
    seen: list = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not self.failed:
            self.failed = True
            request = httpx.Request("POST", "https://api.groq.com")
            raise BadRequestError(
                "tool_use_failed: Tool call validation failed",
                response=httpx.Response(400, request=request),
                body=None,
            )
        self.seen = messages
        return super()._generate(messages, stop, run_manager, **kwargs)


def test_misnamed_tool_call_is_retried_with_a_hint(script):
    model = script(AIMessage("Only plan questions, please."), model_class=FlakyToolModel)
    response = analyst_agent.run_ask(ask("Hi"))
    assert response.answer == "Only plan questions, please."
    assert model.seen[-1].content == analyst_agent.TOOL_CALL_HINT.content


@pytest.mark.parametrize(
    ("name", "args", "summary"),
    [
        ("get_plan", {"scenario": "snowstorm"}, "Read the snowstorm plan for all departments"),
        (
            "run_what_if",
            {"demand_multiplier": 0.8, "shock": "heat_wave", "on_time_target": 0.95},
            "Re-ran the plan with demand -20% and a heat wave and a 95% on-time target",
        ),
        ("run_what_if", {}, "Re-ran the plan with the base settings"),
        (
            "query_service_stats",
            {"metric": "median_days_to_close", "group_by": "neighborhood", "departments": ["PWDx"]},
            "Looked up median days to close by neighborhood for Public Works, 2024",
        ),
    ],
)
def test_trace_summaries_read_as_plain_words(name, args, summary):
    assert analyst_agent._summary(name, args) == summary


def test_311_as_the_service_name_is_not_a_number():
    assert unverified_numbers("The 311 history shows 311 requests.", known({"x": 1})) == []


def test_a_one_word_request_type_suggests_the_full_name():
    out = load(
        analyst_agent.query_service_stats,
        metric="median_days_to_close",
        group_by="neighborhood",
        request_type="pothole",
    )
    assert out["results"][0]["closest_names"]["request_type"][0] == "Request for Pothole Repair"


def test_forecast_interval_level_verifies_80_percent():
    (isd,) = load(analyst_agent.get_forecast, departments=["ISD"])
    k = known_values([json.dumps(isd)], [])
    assert unverified_numbers("The 80% interval runs from 1,216 to 1,766.", k) == []


# ---------- review fixes ----------


def test_small_round_numbers_must_match_exactly():
    k = known({"hires": 9, "total_cost": 20516836})
    assert unverified_numbers("It hires 10 crews.", k) == ["10"]
    assert unverified_numbers("It costs $20M.", k) == ["$20M"]
    assert unverified_numbers("It costs $21M, about $20.5M, not $22M.", k) == ["$22M"]


def test_percents_compare_with_fractions_only():
    k = known({"crews": 21})
    assert unverified_numbers("21% of requests.", k) == ["21%"]


def test_numbers_after_a_minus_sign_or_dash_are_checked():
    k = known({"change": -7.77e6, "low": 3})
    assert unverified_numbers("Costs fall by -$7.77M; between 3–999 crews.", k) == ["999"]
    assert unverified_numbers("A -20% change.", k) == ["-20%"]
    assert unverified_numbers("In 2025-03 nothing changes.", k) == []


def test_neighborhood_shares_count_requests_with_no_neighborhood():
    out = load(
        analyst_agent.query_service_stats,
        metric="request_count",
        group_by="neighborhood",
        limit=25,
    )
    rows = out["results"][0]["rows"]
    total = sum(analyst_agent._requests_2024().values())
    assert rows[0]["share"] == round(rows[0]["request_count"] / total, 4)


def test_trace_summary_survives_odd_arguments():
    assert (
        analyst_agent._summary("run_what_if", {"demand_multiplier": "1.2"}) == "Called run_what_if"
    )
    assert analyst_agent._summary("run_what_if", {"shock": None}) == "Called run_what_if"
    assert analyst_agent._summary("get_plan", {"departments": "BTDT"}) == (
        "Read the base plan for Transportation"
    )


def batch(*calls):
    return AIMessage(
        "",
        tool_calls=[{"name": n, "args": a, "id": f"b{i}"} for i, (n, a) in enumerate(calls)],
    )


def test_a_batch_crossing_the_cap_leaves_its_blocked_calls_out(script):
    script(
        *[call("get_forecast", i, departments=["ISD"]) for i in range(5)],
        batch(("run_what_if", {"demand_multiplier": 1.3}), ("get_forecast", {})),
        AIMessage("never reached"),
    )
    response, stats = analyst_agent.run_ask_with_stats(ask("q"))
    assert [s.tool for s in response.trace] == ["get_forecast"] * 5
    assert response.what_if is None  # run_what_if never ran
    assert response.answer.startswith("I couldn't finish")
    assert stats["llm_calls"] == 6  # not the limiter's own message


def test_a_misnamed_call_counting_toward_the_cap_still_ends_cleanly(script):
    script(
        call("get_plans", 0), *[call("get_forecast", i, departments=["ISD"]) for i in range(1, 8)]
    )
    response = analyst_agent.run_ask(ask("q"))
    assert response.answer.startswith("I couldn't finish")
    assert response.unverified_numbers == []
    assert len(response.trace) == 5  # the misnamed call and the blocked one didn't run


# ---------- eval scoring ----------


def traced(*steps):
    trace = [ToolTraceStep(tool=t, args=a, summary="") for t, a in steps]
    return AskResponse(answer="", trace=trace, what_if=None, unverified_numbers=[])


def row(tools, arguments):
    return SimpleNamespace(expected_tools=tools, expected_arguments=json.dumps(arguments))


def test_score_fills_in_arguments_left_at_their_default():
    expected = row("get_plan", {"get_plan": {"scenario": "base", "departments": ["BTDT"]}})
    s = score(expected, traced(("get_plan", {"departments": ["BTDT"]})))
    assert (s["tools_ok"], s["args_hit"], s["args_scored"]) == (True, 2, 2)


def test_score_takes_the_best_matching_stand_in():
    expected = row(
        "get_plan|run_what_if",
        {"get_plan": {"scenario": "demand_plus_20"}, "run_what_if": {"demand_multiplier": 1.2}},
    )
    both = traced(("get_plan", {"scenario": "demand_plus_20"}), ("run_what_if", {"shock": "none"}))
    assert (score(expected, both)["args_hit"], score(expected, both)["args_scored"]) == (1, 1)
    neither = score(expected, traced(("get_forecast", {})))
    assert (neither["tools_ok"], neither["args_hit"], neither["args_scored"]) == (False, 0, 1)


def test_load_set_rejects_duplicate_ids_and_invalid_values(tmp_path):
    path = tmp_path / "set.csv"
    rows = [
        ["A", "q", "get_plan", json.dumps({"get_plan": {"scenario": "base_plan"}}), ""],
        ["A", "q", "get_plan", "{}", ""],
    ]
    pd.DataFrame(rows, columns=analyst_eval.COLUMNS).to_csv(path, index=False)
    with pytest.raises(ValueError) as error:
        load_set(path)
    assert "row A: duplicate id" in str(error.value)
    assert "valid arguments" in str(error.value) and "base_plan" not in str(error.value)


def test_dev_set_loads():
    assert len(load_set("data/processed/analyst_dev_set.csv")) == 10


# ---------- PR #9 review ----------


def test_target_met_needs_every_department_at_the_target():
    # plan-wide 94.3% passes 0.94, but Public Works and Transportation fall short
    out = load(analyst_agent.run_what_if, on_time_target=0.94)
    assert out["all_departments"]["on_time_pct"] >= 0.94
    assert out["target_met"] is False
    assert out["departments_below_target"] == ["PWDx", "BTDT"]


def test_department_on_time_matches_the_simulator():
    from boston311.forecast.models import load_forecast
    from boston311.planning.scenarios import load_plan
    from boston311.planning.simulator import daily_arrivals, daily_capacity, simulate, sla_shares

    forecast = {
        d.department: {m.month: m.forecast for m in d.months} for d in load_forecast().departments
    }
    for d in load_plan("base").departments:
        crews = {m.month: m.active_crews + m.seasonal for m in d.months}
        sim = simulate(
            daily_arrivals(d.department, forecast[d.department]),
            daily_capacity(d.department, crews),
            sla_shares(d.department),
        )
        rate = sim["on_time"].sum() / sim["eligible"].sum()
        assert analyst_agent._on_time(d) == pytest.approx(rate, abs=1e-4)


def test_a_tool_that_returns_an_error_stays_out_of_the_trace(script):
    script(
        call("run_what_if", 1, demand_multiplier=2.0),
        AIMessage("Demand can only be scaled between 0.5 and 1.5."),
    )
    response, stats = analyst_agent.run_ask_with_stats(ask("What if demand doubles?"))
    assert response.trace == [] and response.what_if is None
    assert stats["tool_calls"] == 0


def rate_limited(message, fail_times):
    """Stands in for run_ask_with_stats: raises Groq's 429 with message, then answers."""
    from groq import RateLimitError

    calls = []

    def run(messages):
        calls.append(messages)
        if len(calls) <= fail_times:
            request = httpx.Request("POST", "https://api.groq.com")
            response = httpx.Response(429, request=request)
            raise RateLimitError(message, response=response, body=None)
        return traced(), {}

    return run, calls


def test_eval_waits_out_one_per_minute_rate_limit(monkeypatch):
    run, calls = rate_limited("Rate limit reached ... on tokens per minute (TPM)", 1)
    monkeypatch.setattr(analyst_eval, "run_ask_with_stats", run)
    monkeypatch.setattr(analyst_eval, "RATE_LIMIT_WAIT", 0)
    response, _ = analyst_eval.ask("q")
    assert len(calls) == 2 and response.trace == []


def test_eval_does_not_wait_on_the_daily_limit(monkeypatch):
    from groq import RateLimitError

    run, calls = rate_limited("Rate limit reached ... on tokens per day (TPD): Limit 200000", 1)
    monkeypatch.setattr(analyst_eval, "run_ask_with_stats", run)
    monkeypatch.setattr(analyst_eval, "RATE_LIMIT_WAIT", 3600)  # a wait would hang the test
    with pytest.raises(RateLimitError):
        analyst_eval.ask("q")
    assert len(calls) == 1


@pytest.mark.parametrize("error", [KeyError(), TimeoutError(), AssertionError()])
def test_eval_records_errors_with_empty_messages(monkeypatch, error):
    def fail(question):
        raise error

    monkeypatch.setattr(analyst_eval, "ask", fail)
    questions = pd.DataFrame(
        [{"id": "X", "question": "q", "expected_tools": "get_plan", "expected_arguments": "{}"}] * 2
    ).assign(expected_facts="")
    records = analyst_eval.run(questions)  # the run carries on past the bad question
    assert [r["error"] for r in records] == [f"{type(error).__name__}: "] * 2


def test_plan_wide_figures_are_labelled_all_departments():
    out = load(analyst_agent.run_what_if, demand_multiplier=1.2, departments=["BTDT"])
    assert "kpis" not in out and "change_from_base" not in out
    assert set(out["all_departments"]) >= {"total_cost", "on_time_pct", "change_from_base"}
    (btdt,) = out["departments"]
    # Transportation's own figures differ from the whole plan's, which the answer mixed up
    assert btdt["totals"]["cost"] < out["all_departments"]["total_cost"]
    assert btdt["totals"]["on_time_pct"] != out["all_departments"]["on_time_pct"]


def test_get_plan_states_the_target_it_was_planned_to():
    assert load(analyst_agent.get_plan, scenario="base")["on_time_target"] == 0.9
    assert "on_time_target" not in load(analyst_agent.get_plan, scenario="hold_flat")
    k = known_values([analyst_agent.get_plan.invoke({"scenario": "demand_plus_20"})], [])
    assert unverified_numbers("Parks still meets the 90% target.", k) == []


def test_percentage_points_compare_with_fraction_changes():
    k = known({"change_from_base": {"on_time_pct": -0.0193}})
    for text in ("falls by 1.9 percentage points", "falls 1.9 points", "down 1.9 pp"):
        assert unverified_numbers(text, k) == [], text
    assert unverified_numbers("falls by 2.4 points", k) == ["2.4 points"]


def test_citation_marks_are_removed_from_the_answer(script):
    script(AIMessage("The plan meets its target【run_what_if†result】."))
    assert analyst_agent.run_ask(ask("q")).answer == "The plan meets its target."
