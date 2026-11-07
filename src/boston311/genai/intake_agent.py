"""Intake agent: splits a report into problems, searches and checks request types with two
read-only tools, and returns routing cards. Falls back to the single-call pipeline."""

import json
import logging
from difflib import get_close_matches
from functools import cache

from groq import BadRequestError
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware, wrap_model_call
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from boston311.api.schemas import ChatMessage, IntakeResponse, ToolTraceStep
from boston311.config import DEPARTMENTS
from boston311.data.aggregate import Metric, query_service_stats
from boston311.genai import llm
from boston311.genai.intake_pipeline import draft_schema, run_pipeline, to_langchain, to_response
from boston311.genai.kb import load_kb, request_type_table
from boston311.genai.retriever import search

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 6  # per turn, including the final answer
MAX_FAILED_VALIDATIONS = 2
MAX_TOOL_CALL_RETRIES = 2
# Groq's 400 codes for a reply that isn't a valid call to a declared tool
RETRYABLE_GROQ_ERRORS = ("tool_use_failed", "output_parse_failed")
STATS_YEAR = 2024
TOOL_NAMES = {"search_request_types", "get_request_types"}  # not the answer tool

AGENT_PROMPT = """You are the intake assistant for Boston 311. A resident describes one or \
more problems in plain English, and you file one request per problem.
Only four departments are in scope: Public Works (streets, sidewalks, lights, trash, \
graffiti), Transportation (parking, signs, signals), Parks & Recreation (parks and trees), and \
Inspectional Services (housing and building conditions such as heat, pests and unsafe buildings).
1. Split the message into separate problems. Call search_request_types once, with one short \
phrase per problem.
2. Call get_request_types once with the candidate types you are choosing between, and the \
neighborhood if the resident gave one, to check what each type covers and how long it takes.
3. Finish by calling the IntakeDraft tool, named exactly that. Always finish this way, even when \
every problem is out of scope; never answer in plain text.
request_type is an exact name returned by search_request_types, or "out_of_scope" for a \
problem that belongs to another department or agency.
Ask a follow_up_question only when you cannot choose between request types for a problem; then \
leave that problem out of requests. A missing street address is not a reason to ask. \
Otherwise follow_up_question is null.
location is the place as the resident gave it, or null. details is one line for the crew.
reply is a short, friendly message to the resident saying what you filed and how long that \
kind of request usually takes to close, or what you need from them.
Never invent request types or numbers. Use at most 4 tool calls."""


@cache
def _neighborhoods() -> list[str]:
    rows = query_service_stats("request_count", "neighborhood", {"year": STATS_YEAR}, limit=100)
    return [r["neighborhood"] for r in rows]


def _stat(metric: Metric, request_type: str, neighborhood: str | None = None):
    filters = {"request_type": request_type, "year": STATS_YEAR}
    if neighborhood:
        filters["neighborhood"] = neighborhood
    rows = query_service_stats(metric, "request_type", filters, limit=1)
    return rows[0][metric] if rows else None


@tool
def search_request_types(queries: list[str]) -> str:
    """Find the 5 closest Boston 311 request types for each problem. Pass one short phrase per
    problem in the resident's message."""
    return json.dumps({q: search(q) for q in queries})


@tool
def get_request_types(request_types: list[str], neighborhood: str | None = None) -> str:
    """For each request type: its department, what the crew needs from the resident, and 2024
    median days to close and on-time rate, citywide and in the neighborhood if one is given."""
    table, kb = request_type_table(), {e["request_type"]: e for e in load_kb()}
    out: dict = {}
    if neighborhood:
        known = {n.lower(): n for n in _neighborhoods()}
        if neighborhood.lower() in known:
            neighborhood = known[neighborhood.lower()]
        else:
            closest = get_close_matches(neighborhood, _neighborhoods(), n=3, cutoff=0.5)
            out["unknown_neighborhood"] = {"given": neighborhood, "closest": closest}
            neighborhood = None
    out["request_types"] = []
    for t in request_types:
        if t not in table.index:
            out["request_types"].append({"request_type": t, "error": "unknown request type"})
            continue
        days = table.loc[t, "median_days_to_close"]
        info = {
            "request_type": t,
            "department": DEPARTMENTS[table.loc[t, "department"]]["name"],
            "crew_needs": kb[t]["crew_needs"],
            "median_days_to_close": None if days != days else float(days),  # NaN: none closed
            "on_time_rate": _stat("on_time_rate", t),
        }
        if neighborhood:
            info[neighborhood] = {
                "median_days_to_close": _stat("median_days_to_close", t, neighborhood),
                "on_time_rate": _stat("on_time_rate", t, neighborhood),
            }
        out["request_types"].append(info)
    return json.dumps(out)


TOOL_CALL_HINT = HumanMessage(
    "Your last reply was not a valid tool call. Call one of the provided tools by its exact "
    "name: search_request_types, get_request_types or IntakeDraft. To answer, call IntakeDraft."
)


@wrap_model_call
def retry_bad_tool_call(request, handler):
    """gpt-oss on Groq sometimes names a tool wrongly ("commentary", "intake") or answers in
    plain text, and Groq rejects the reply with a 400. Ask again with a hint naming the tools;
    a plain retry tends to repeat the mistake."""
    for attempt in range(MAX_TOOL_CALL_RETRIES + 1):
        try:
            if attempt == 0:
                return handler(request)
            return handler(request.override(messages=[*request.messages, TOOL_CALL_HINT]))
        except BadRequestError as error:
            if attempt == MAX_TOOL_CALL_RETRIES or not any(
                c in str(error) for c in RETRYABLE_GROQ_ERRORS
            ):
                raise
            logger.info("retrying a malformed tool call: %s", error)


@cache
def _agent_draft_schema():
    return draft_schema(list(request_type_table().index), enum=False)


def _summary(name: str, args: dict) -> str:
    if name == "search_request_types":
        n = len(args.get("queries", []))
        return f"Searched request types for {n} problem{'s' * (n != 1)}"
    n = len(args.get("request_types", []))
    where = f" in {args['neighborhood']}" if args.get("neighborhood") else ""
    return f"Looked up {n} request type{'s' * (n != 1)}{where}"


def run_agent(messages: list[ChatMessage]) -> tuple[IntakeResponse, dict]:
    """Raises when the agent gives no valid answer (2 bad answers, the tool-call cap, no answer)."""
    failures = 0

    def on_bad_answer(error: Exception) -> str:
        nonlocal failures
        failures += 1
        if failures >= MAX_FAILED_VALIDATIONS:
            raise error
        return f"That answer did not validate: {error}. Answer again with valid request types."

    schema = _agent_draft_schema()
    agent = create_agent(
        llm.chat_model(),
        [search_request_types, get_request_types],
        system_prompt=AGENT_PROMPT,
        response_format=ToolStrategy(schema, handle_errors=on_bad_answer),
        middleware=[
            ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS, exit_behavior="end"),
            retry_bad_tool_call,
        ],
    )
    history = to_langchain(messages)
    result = agent.invoke({"messages": history})
    if result.get("structured_response") is None:
        raise RuntimeError("intake agent stopped without an answer")
    new = [m for m in result["messages"][len(history) :] if isinstance(m, AIMessage)]
    calls = [c for m in new for c in m.tool_calls if c["name"] in TOOL_NAMES]
    trace = [
        ToolTraceStep(tool=c["name"], args=c["args"], summary=_summary(c["name"], c["args"]))
        for c in calls
    ]
    stats = {
        "tool_calls": len(calls),
        "llm_calls": len(new),
        "uncached_tokens": llm.uncached_tokens(new),
    }
    return to_response(result["structured_response"], trace), stats


def run_intake_with_stats(messages: list[ChatMessage]) -> tuple[IntakeResponse, dict]:
    try:
        return run_agent(messages)
    except Exception:
        logger.warning("intake agent failed; answering with the pipeline", exc_info=True)
    response, stats = run_pipeline(messages)
    return response.model_copy(update={"fallback_used": True}), stats


def run_intake(messages: list[ChatMessage]) -> IntakeResponse:
    """Route the conversation's problems to request types; the server fills department and queue."""
    return run_intake_with_stats(messages)[0]
