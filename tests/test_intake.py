import json

import httpx
import pandas as pd
import pytest
from groq import BadRequestError
from langchain.agents.structured_output import StructuredOutputValidationError
from langchain_core.globals import set_llm_cache
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from boston311.api.schemas import ChatMessage
from boston311.config import PROCESSED_DIR
from boston311.eval.intake_eval import load_set, parse_problems, summarize
from boston311.genai import intake_agent, intake_pipeline, kb, llm
from boston311.genai.kb import request_type_table
from boston311.genai.llm import CountingCache, uncached_tokens


def test_cache_counts_only_misses(tmp_path):
    cache = CountingCache(str(tmp_path / "llm.sqlite"))
    set_llm_cache(cache)
    try:
        model = GenericFakeChatModel(messages=iter([AIMessage("one"), AIMessage("two")]))
        assert model.invoke("hi").content == "one"
        assert model.invoke("hi").content == "one"  # served from the disk cache
        assert cache.misses == 1
    finally:
        set_llm_cache(None)


def test_uncached_tokens_subtracts_cache_reads():
    messages = [
        AIMessage(
            "a",
            usage_metadata={
                "input_tokens": 1000,
                "output_tokens": 50,
                "total_tokens": 1050,
                "input_token_details": {"cache_read": 800},
            },
        ),
        AIMessage("b", usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}),
    ]
    assert uncached_tokens(messages) == 200 + 50 + 10 + 5


class ScriptedStructured:
    """Stands in for llm.structured(model, schema): returns the next scripted reply."""

    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def __call__(self, model, schema):
        self.schema = schema
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        parsed = next(self.replies)(self.schema)
        return {"raw": AIMessage(""), "parsed": parsed, "parsing_error": None}


TYPES = pd.DataFrame(
    {
        "request_type": ["Request for Pothole Repair", "Rodent Activity", "Sidewalk Repair"],
        "department": ["PWDx", "ISD", "PWDx"],
        "queue": ["PWDx_Pothole", "ISD_Environmental Services", "PWDx_Highway Maintenance"],
    }
)


def kb_reply(*types):
    def build(schema):
        return schema(
            types=[
                {
                    "request_type": t,
                    "description": f"{t} description",
                    "phrasings": [f"{t} phrasing {i}" for i in range(4)],
                    "crew_needs": "Exact location",
                }
                for t in types
            ]
        )

    return build


def test_build_kb_asks_again_for_types_the_model_skipped(monkeypatch):
    fake = ScriptedStructured(
        [kb_reply("Request for Pothole Repair", "Rodent Activity"), kb_reply("Sidewalk Repair")]
    )
    monkeypatch.setattr(kb.llm, "structured", fake)
    entries = kb.build_kb(
        TYPES, {"Request for Pothole Repair": ["SINKHOLE"]}, None, frozenset({"Sidewalk Repair"})
    )
    assert [e["request_type"] for e in entries] == sorted(TYPES["request_type"])
    assert len(fake.calls) == 2
    assert "SINKHOLE" in fake.calls[0][-1].content
    assert (
        "Sidewalk Repair (department: Public Works, queue: PWDx_Highway Maintenance, staff only)"
        in (fake.calls[0][-1].content)
    )
    assert (
        "Rodent Activity (department: Inspectional Services, queue: ISD_Environmental Services)"
        in (fake.calls[0][-1].content)
    )


def test_build_kb_fails_when_a_type_never_comes_back(monkeypatch):
    fake = ScriptedStructured([kb_reply("Rodent Activity")] * 3)
    monkeypatch.setattr(kb.llm, "structured", fake)
    with pytest.raises(ValueError, match="Sidewalk Repair"):
        kb.build_kb(TYPES, {}, model=None)


TRASH, RAT = "Missed Trash/Recycling/Yard Waste/Bulk Item", "Rodent Activity"
CANDIDATES = [{"request_type": t, "description": f"{t} description"} for t in (TRASH, RAT)]
USER = [ChatMessage(role="user", content="Trash wasn't picked up and there's a dead rat")]


def draft(*types, follow_up=None):
    def build(schema):
        requests = [{"request_type": t, "location": "Adams St", "details": t} for t in types]
        return schema(requests=requests, follow_up_question=follow_up, reply="Filed.")

    return build


@pytest.fixture
def offline(monkeypatch):
    """No network: fake retrieval and no real chat model."""
    monkeypatch.setattr(intake_pipeline, "search", lambda query, k=5: CANDIDATES)
    monkeypatch.setattr(llm, "chat_model", lambda model=None: None)


def test_pipeline_fills_routing_from_the_lookup_table(offline, monkeypatch):
    monkeypatch.setattr(llm, "structured", ScriptedStructured([draft(TRASH, RAT)]))
    response, stats = intake_pipeline.run_pipeline(USER)
    table = request_type_table()
    assert [(r.department, r.queue) for r in response.requests] == [
        (table.loc[TRASH, "department"], table.loc[TRASH, "queue"]),
        (table.loc[RAT, "department"], table.loc[RAT, "queue"]),
    ]
    assert response.requests[0].typical_days_to_close == table.loc[TRASH, "median_days_to_close"]
    assert not response.out_of_scope and not response.fallback_used
    assert stats["llm_calls"] == 1


def test_pipeline_only_allows_retrieved_candidates(offline, monkeypatch):
    fake = ScriptedStructured([draft(TRASH)])
    monkeypatch.setattr(llm, "structured", fake)
    intake_pipeline.run_pipeline(USER)
    with pytest.raises(ValidationError):
        fake.schema(
            requests=[{"request_type": "Sidewalk Repair", "location": None, "details": ""}],
            follow_up_question=None,
            reply="",
        )


def test_out_of_scope_message_routes_nothing(offline, monkeypatch):
    monkeypatch.setattr(llm, "structured", ScriptedStructured([draft("out_of_scope")]))
    response, _ = intake_pipeline.run_pipeline(USER)
    assert response.out_of_scope and response.requests == []


def test_follow_up_is_not_out_of_scope(offline, monkeypatch):
    fake = ScriptedStructured([draft(follow_up="Is the rat inside or outside?")])
    monkeypatch.setattr(llm, "structured", fake)
    response, _ = intake_pipeline.run_pipeline(USER)
    assert not response.out_of_scope and response.follow_up_question


@pytest.mark.parametrize("written", ["null", "None", "", "  ", "N/A"])
def test_null_like_follow_up_text_means_no_question(offline, monkeypatch, written):
    # gpt-oss sometimes writes "null" as text instead of leaving the field empty
    monkeypatch.setattr(llm, "structured", ScriptedStructured([draft(TRASH, follow_up=written)]))
    response, _ = intake_pipeline.run_pipeline(USER)
    assert response.follow_up_question is None and not response.out_of_scope

    monkeypatch.setattr(llm, "structured", ScriptedStructured([draft(follow_up=written)]))
    response, _ = intake_pipeline.run_pipeline(USER)
    assert response.follow_up_question is None and response.out_of_scope  # nothing filed


def test_a_real_follow_up_question_is_kept_and_trimmed(offline, monkeypatch):
    fake = ScriptedStructured([draft(follow_up="  Is the rat inside or outside?  ")])
    monkeypatch.setattr(llm, "structured", fake)
    response, _ = intake_pipeline.run_pipeline(USER)
    assert response.follow_up_question == "Is the rat inside or outside?"


class FakeToolModel(GenericFakeChatModel):
    """Scripted chat model that accepts tools, for driving create_agent offline."""

    def bind_tools(self, tools, **kwargs):
        return self


def call(name, i, **args):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{i}"}])


def answer(i, *types):
    requests = [{"request_type": t, "location": "Adams St", "details": t} for t in types]
    return call("IntakeDraft", i, requests=requests, follow_up_question=None, reply="Filed.")


@pytest.fixture
def agent_model(monkeypatch, offline):
    monkeypatch.setattr(intake_agent, "search", lambda query, k=5: CANDIDATES)

    def use(*script):
        model = FakeToolModel(messages=iter(script))
        monkeypatch.setattr(llm, "chat_model", lambda model_name=None: model)

    return use


def test_agent_routes_two_problems_and_shows_its_work(agent_model):
    agent_model(
        call("search_request_types", 1, queries=["missed trash", "dead rat"]),
        call("get_request_types", 2, request_types=[TRASH, RAT], neighborhood="Dorchester"),
        answer(3, TRASH, RAT),
    )
    response, stats = intake_agent.run_agent(USER)
    assert [r.request_type for r in response.requests] == [TRASH, RAT]
    assert [r.department for r in response.requests] == ["PWDx", "ISD"]
    assert [s.summary for s in response.trace] == [
        "Searched request types for 2 problems",
        "Looked up 2 request types in Dorchester",
    ]
    assert stats["tool_calls"] == 2 and not response.fallback_used


def test_two_invalid_answers_fall_back_to_the_pipeline(agent_model, monkeypatch):
    agent_model(answer(1, "Made-up Type"), answer(2, "Made-up Type"))
    with pytest.raises(StructuredOutputValidationError):
        intake_agent.run_agent(USER)

    agent_model(answer(1, "Made-up Type"), answer(2, "Made-up Type"))
    monkeypatch.setattr(llm, "structured", ScriptedStructured([draft(TRASH)]))
    response = intake_agent.run_intake(USER)
    assert response.fallback_used
    assert [r.request_type for r in response.requests] == [TRASH]


def test_one_invalid_answer_gets_a_retry(agent_model):
    agent_model(answer(1, "Made-up Type"), answer(2, RAT))
    response, _ = intake_agent.run_agent(USER)
    assert [r.request_type for r in response.requests] == [RAT]


def test_tool_call_cap_falls_back_to_the_pipeline(agent_model, monkeypatch):
    searches = [call("search_request_types", i, queries=["trash"]) for i in range(10)]
    agent_model(*searches)
    with pytest.raises(RuntimeError, match="stopped without an answer"):
        intake_agent.run_agent(USER)

    agent_model(*searches)
    monkeypatch.setattr(llm, "structured", ScriptedStructured([draft(TRASH)]))
    assert intake_agent.run_intake(USER).fallback_used


def test_misspelled_neighborhood_suggests_the_closest_names():
    out = json.loads(
        intake_agent.get_request_types.invoke(
            {"request_types": [RAT, "Not A Type"], "neighborhood": "Dorchster"}
        )
    )
    assert "Dorchester" in out["unknown_neighborhood"]["closest"]
    assert out["request_types"][0]["department"] == "Inspectional Services"
    assert out["request_types"][1]["error"] == "unknown request type"


def test_parse_problems_splits_problems_then_alternatives():
    assert parse_problems(f"{TRASH} ; {RAT}|Pick up Dead Animal") == [
        [TRASH],
        [RAT, "Pick up Dead Animal"],
    ]
    assert parse_problems("") == []


def test_eval_summary_counts():
    def rec(problems, predicted, follow=False, asked=False, oos=False, **extra):
        stats = {"tool_calls": 2, "llm_calls": 3, "uncached_tokens": 1000, "fallback": False}
        return (
            {
                "problems": problems,
                "predicted": predicted,
                "follow_up_expected": follow,
                "asked": asked,
                "out_of_scope": oos,
            }
            | stats
            | extra
        )

    dead = "Pick up Dead Animal"
    records = [
        rec([[TRASH], [RAT]], [TRASH, dead]),  # 1 of 2 types, split right
        rec([[RAT, dead]], [dead]),  # an accepted alternative counts as correct
        rec([[RAT, dead], [RAT]], [RAT, dead]),  # needs RAT for the 2nd problem, dead for the 1st
        rec([], [], oos=True),  # out of scope, handled
        rec([], [], follow=True, asked=True),  # wanted follow-up, got it
        rec([[RAT]], [RAT], asked=True),  # an unneeded follow-up
        {"problems": [[RAT]], "follow_up_expected": False, "error": "BadRequestError"},
    ]
    s = summarize(records)
    assert s["type correct"] == "5/6"
    assert s["department correct"] == "5/6"  # the dead-animal type is PWDx, not ISD
    assert s["queue correct"] == "5/6"
    assert s["split correct"] == "2/2"
    assert (s["follow-up precision"], s["follow-up recall"]) == ("1/2", "1/1")
    assert (s["out of scope correct"], s["errors"]) == ("1/1", 1)
    assert s["uncached tokens / msg"] == 1000


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


def test_misnamed_tool_call_is_retried_with_a_hint(agent_model, monkeypatch):
    model = FlakyToolModel(messages=iter([answer(1, RAT)]))
    monkeypatch.setattr(llm, "chat_model", lambda model_name=None: model)
    response, _ = intake_agent.run_agent(USER)
    assert [r.request_type for r in response.requests] == [RAT]
    assert model.seen[-1].content == intake_agent.TOOL_CALL_HINT.content


def test_dev_set_messages_are_not_in_the_retrieval_corpus():
    # working assumption 8; catches exact copies only, not paraphrases
    dev = pd.read_csv(PROCESSED_DIR / "intake_dev_set.csv")
    phrasings = {p.strip().lower() for e in kb.load_kb() for p in e["phrasings"]}
    assert not {m.strip().lower() for m in dev["message"]} & phrasings


def test_trace_names_only_known_neighborhoods():
    lookup = {"request_types": [RAT], "neighborhood": "Southie"}
    assert intake_agent._summary("get_request_types", lookup) == "Looked up 1 request type"
    lookup["neighborhood"] = "dorchester"
    assert (
        intake_agent._summary("get_request_types", lookup)
        == "Looked up 1 request type in dorchester"
    )


def write_set(tmp_path, rows):
    path = tmp_path / "set.csv"
    pd.DataFrame(
        rows, columns=["id", "message", "expected_request_types", "expects_follow_up"]
    ).to_csv(path, index=False)
    return path


def test_load_set_accepts_yes_no_and_one_zero(tmp_path):
    path = write_set(
        tmp_path, [[1, "a", RAT, "no"], [2, "b", "", "Yes"], [3, "c", "", 1], [4, "d", RAT, 0]]
    )
    assert list(load_set(path)["expects_follow_up"]) == [False, True, True, False]


def test_load_set_names_bad_rows_without_showing_labels(tmp_path):
    path = write_set(tmp_path, [[1, "a", RAT, "maybe"], [2, "b", "Made-up Type", "no"]])
    with pytest.raises(ValueError) as error:
        load_set(path)
    message = str(error.value)
    assert "row 1: expects_follow_up" in message and "row 2:" in message
    assert "Made-up Type" not in message and "maybe" not in message


def test_load_set_needs_the_columns(tmp_path):
    path = tmp_path / "set.csv"
    pd.DataFrame({"id": [1], "message": ["a"], "expected_types": [RAT]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        load_set(path)


def test_dev_set_loads():
    assert len(load_set(PROCESSED_DIR / "intake_dev_set.csv")) == 12
