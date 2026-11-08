"""Planning analyst agent: answers questions about the 2025 plan, the forecast and the 311 history
with four read-only tools, then flags any number in its answer that no tool returned and the
user didn't write."""

import json
import logging
import math
import re
from difflib import get_close_matches
from functools import cache, lru_cache

import pandas as pd
from groq import BadRequestError
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware, wrap_model_call
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import ValidationError

from boston311.api.schemas import (
    AskResponse,
    ChatMessage,
    Department,
    DepartmentPlan,
    PlanResult,
    Scenario,
    Shock,
    SolveRequest,
    ToolTraceStep,
)
from boston311.config import DEPARTMENTS, PROCESSED_DIR
from boston311.data.aggregate import GroupBy, Metric
from boston311.data.aggregate import query_service_stats as stats_query
from boston311.forecast.models import FORECAST_PATH, load_forecast
from boston311.genai import llm
from boston311.genai.intake_pipeline import to_langchain
from boston311.planning.optimizer import solve_plan
from boston311.planning.scenarios import SCENARIOS, load_plan

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 6  # per turn
MAX_TOOL_CALL_RETRIES = 2
RETRYABLE_GROQ_ERRORS = ("tool_use_failed", "output_parse_failed")
# how ToolCallLimitMiddleware answers the calls it blocks
LIMIT_ERRORS = ("Tool call limit exceeded", "Execution stopped before this tool call")
STATS_YEARS = (2023, 2024)
MAX_ROWS = 25
NAMES = {code: d["name"] for code, d in DEPARTMENTS.items()}

AGENT_PROMPT = """You are the planning analyst for Boston 311 crew planning. Operations leads ask \
about the 2025 crew plan, the demand forecast, what-if scenarios and past service levels.
Departments: PWDx Public Works, BTDT Transportation, PARK Parks & Recreation, ISD Inspectional \
Services.
Tools:
- get_plan: a precomputed 2025 plan. Scenarios: base (90% on-time target), hold_flat (January \
crews all year, the baseline), demand_plus_20, demand_minus_20, snowstorm, heat_wave. Monthly \
crews, hires, releases, Parks seasonal crews, capacity, forecast, simulated on-time rate and cost, \
yearly totals per department, and all_departments: the KPIs of all four departments together, \
including the saving and on-time gain against holding January crews flat.
- run_what_if: re-solves the plan for a demand multiplier (0.5 to 1.5), a shock (none, snowstorm, \
heat_wave) and an on-time target (0.5 to 0.99). Returns the same plan data, target_met (true only \
when every department reaches the target) and the change from the base plan, for all departments \
and per department. Use get_plan instead when a named scenario matches the question.
- get_forecast: the monthly 2025 forecast with its 80% interval, the method, the backtest error \
and the 2024 total for comparison.
- query_service_stats: the 2023 or 2024 311 history: request counts (with shares), on-time rate \
or median days to close, grouped by department, neighborhood, request type, source or month.
Rules:
1. Every number in your answer must come from a tool result or from the user's question. Never \
add, subtract or divide numbers yourself; use the totals, shares and changes the tools return.
2. Rates and shares come as fractions (0.921): write them as percentages (92.1%). Money can be \
written in millions ($15.91M).
3. Pass departments to keep results small. Use at most 4 tool calls.
4. all_departments figures are for the four departments together. When the question is about one \
department, use that department's totals and monthly figures, and say "the whole plan" for any \
all_departments figure you also give.
5. If target_met is false, say the plan could not reach the on-time target and name the \
departments_below_target.
6. Answer in 2 to 5 plain sentences, without tables or headings, and say which plan or data each \
number comes from.
7. If a result has no rows and lists closest_names, call the tool again with one of those names.
8. If the question is not about the plan, the forecast or the 311 history, say that is all you \
can answer."""

TOOL_CALL_HINT = HumanMessage(
    "Your last reply was not a valid tool call. Call one of the provided tools by its exact "
    "name: get_plan, run_what_if, get_forecast or query_service_stats, or answer in plain text."
)


def _dump(data) -> str:
    return json.dumps(data, separators=(",", ":"))


def _error(message: str) -> str:
    return _dump({"error": message})


# ---------- tools ----------


@tool
def get_forecast(departments: list[Department] | None = None) -> str:
    """The monthly 2025 demand forecast per department with its 80% interval, the forecast
    method, its backtest error (a fraction) and the 2024 total. All departments when none given."""
    methods = pd.read_parquet(FORECAST_PATH).groupby("department")["method"].first()
    actual_2024 = _requests_2024()
    out = []
    for d in load_forecast(departments or None).departments:
        total = sum(m.forecast for m in d.months)
        out.append(
            {
                "department": d.department,
                "name": NAMES[d.department],
                "method": methods[d.department],
                "backtest_mape": d.backtest_mape,
                "months": [m.month for m in d.months],
                "forecast": [round(m.forecast) for m in d.months],
                "lower": [round(m.lower) for m in d.months],
                "upper": [round(m.upper) for m in d.months],
                "interval": 0.8,
                "total_2025": round(total),
                "total_2024": actual_2024[d.department],
                "change_vs_2024": round(total / actual_2024[d.department] - 1, 4),
            }
        )
    return _dump(out)


@tool
def query_service_stats(
    metric: Metric,
    group_by: GroupBy,
    departments: list[Department] | None = None,
    request_type: str | None = None,
    neighborhood: str | None = None,
    source: str | None = None,
    year: int = 2024,
    limit: int = 10,
) -> str:
    """311 history (2023 or 2024): request_count, on_time_rate (a fraction) or
    median_days_to_close, grouped by department, neighborhood, request_type, source or month and
    sorted largest first (months in order). One result per department given, or all four
    departments together when none given. request_count rows include each group's share.
    When the question is about one kind of request (potholes, rodents, street lights), pass
    request_type, e.g. "Request for Pothole Repair"; a partial name returns closest_names.
    neighborhood and source filter the same way."""
    if year not in STATS_YEARS:
        return _error(f"year must be one of {list(STATS_YEARS)}")
    limit = max(1, min(int(limit), MAX_ROWS))
    filters = {"request_type": request_type, "neighborhood": neighborhood, "source": source}
    filters = {k: v for k, v in filters.items() if v} | {"year": year}
    results = []
    for code in departments or [None]:
        f = filters | ({"department": code} if code else {})
        try:
            rows = stats_query(metric, group_by, f, limit)
            if metric == "request_count" and rows:
                # every request has a department, so this total includes requests with no
                # value for group_by (e.g. no neighborhood)
                total = sum(r["request_count"] for r in stats_query(metric, "department", f, 10))
                rows = [r | {"share": round(r["request_count"] / total, 4)} for r in rows]
        except ValueError as error:
            return _error(str(error))
        result = {"department": code or "all", "rows": rows}
        if not rows:
            result["closest_names"] = _closest(request_type, neighborhood)
        results.append(result)
    return _dump({"metric": metric, "group_by": group_by, "filters": filters, "results": results})


@tool
def get_plan(scenario: Scenario = "base", departments: list[Department] | None = None) -> str:
    """A precomputed 2025 crew plan: KPIs for all departments, and monthly crews, hires,
    releases, seasonal crews, capacity, forecast, on-time rate and cost with yearly totals for
    the departments asked (all when none given)."""
    summary = _plan_summary(load_plan(scenario), departments)
    if scenario != "hold_flat":  # the baseline isn't planned to a target
        summary["on_time_target"] = SCENARIOS[scenario].on_time_target
    return _dump(summary)


@tool
def run_what_if(
    demand_multiplier: float = 1.0,
    shock: Shock = "none",
    on_time_target: float = 0.9,
    departments: list[Department] | None = None,
) -> str:
    """Re-solve the 2025 plan with demand x demand_multiplier (0.5-1.5), a shock (none,
    snowstorm, heat_wave) and an on-time target (0.5-0.99). Returns the plan, target_met, and
    the change from the base plan in KPIs and per-department totals."""
    try:
        request = SolveRequest(
            demand_multiplier=demand_multiplier, shock=shock, on_time_target=on_time_target
        )
    except ValidationError as error:
        first = error.errors()[0]
        return _error(f"{first['loc'][0]}: {first['msg']}")
    plan = _solve(request.demand_multiplier, request.shock, request.on_time_target)
    base = _plan_summary(load_plan("base"), departments)
    summary = _plan_summary(plan, departments)
    summary["request"] = request.model_dump()
    # the planner aims each department at the target, so every department has to reach it
    below = [d.department for d in plan.departments if _on_time(d) < request.on_time_target]
    summary["target_met"] = not below
    summary["departments_below_target"] = below
    summary["all_departments"]["change_from_base"] = {
        k: round(summary["all_departments"][k] - base["all_departments"][k], 4)
        for k in ("total_cost", "overdue_cost", "on_time_pct")
    }
    for dept, base_dept in zip(summary["departments"], base["departments"], strict=True):
        dept["change_from_base"] = {
            k: round(v - base_dept["totals"][k], 4) for k, v in dept["totals"].items()
        }
    return _dump(summary)


TOOLS = [get_plan, run_what_if, get_forecast, query_service_stats]
TOOL_NAMES = {t.name for t in TOOLS}


@lru_cache(maxsize=32)
def _solve(demand_multiplier: float, shock: str, on_time_target: float) -> PlanResult:
    return solve_plan(
        SolveRequest(
            demand_multiplier=demand_multiplier, shock=shock, on_time_target=on_time_target
        )
    )


def _on_time(department: DepartmentPlan) -> float:
    """The department's yearly simulated on-time rate. Eligible requests are a fixed share of
    each month's demand, so the demand-weighted monthly rate is the simulator's yearly rate."""
    months = department.months
    return sum(m.forecast * m.on_time_pct for m in months) / sum(m.forecast for m in months)


def _plan_summary(plan: PlanResult, departments: list[str] | None) -> dict:
    kpis = {
        k: round(v, 4) if k.endswith("on_time_pct") else round(v)
        for k, v in plan.kpis.model_dump().items()
    }
    # the headline comparison, so the model never has to subtract
    kpis["saving_vs_hold_flat"] = kpis["baseline_total_cost"] - kpis["total_cost"]
    kpis["on_time_gain_vs_hold_flat"] = round(kpis["on_time_pct"] - kpis["baseline_on_time_pct"], 4)
    out = []
    for d in plan.departments:
        if departments and d.department not in departments:
            continue
        m = d.months

        def col(field, digits=None, months=m):
            return [round(getattr(x, field), digits) for x in months]

        working = [x.active_crews + x.seasonal for x in m]
        out.append(
            {
                "department": d.department,
                "name": NAMES[d.department],
                "months": [x.month for x in m],
                "crews": col("active_crews"),
                "hires": col("hires"),
                "releases": col("releases"),
                "seasonal": col("seasonal"),
                "capacity": col("capacity"),
                "forecast": col("forecast"),
                "on_time_pct": col("on_time_pct", 3),
                "cost": col("cost"),
                "totals": {
                    "on_time_pct": round(_on_time(d), 4),
                    "cost": round(sum(x.cost for x in m)),
                    "hires": sum(x.hires for x in m),
                    "releases": sum(x.releases for x in m),
                    "seasonal_crew_months": sum(x.seasonal for x in m),
                    "peak_working_crews": max(working),
                    "january_crews": m[0].active_crews,
                    "december_crews": m[-1].active_crews,
                },
            }
        )
    # plan-wide figures sit under all_departments, so a department's own figures (its totals)
    # can't be mistaken for them
    return {"scenario": plan.scenario, "all_departments": kpis, "departments": out}


@cache
def _requests_2024() -> dict[str, int]:
    monthly = pd.read_csv(PROCESSED_DIR / "monthly_demand.csv")
    year = monthly[monthly["month"].str.startswith("2024")]
    return {k: int(v) for k, v in year.groupby("department")["requests"].sum().items()}


@cache
def _known_names() -> tuple[list[str], list[str]]:
    types = list(pd.read_csv(PROCESSED_DIR / "request_types.csv")["request_type"])
    rows = stats_query("request_count", "neighborhood", {"year": 2024}, 100)
    return types, [r["neighborhood"] for r in rows]


def _suggest(given: str, names: list[str]) -> list[str]:
    """Names containing every word given ("pothole" -> Request for Pothole Repair), then the
    closest spellings."""
    words = given.lower().split()
    containing = [n for n in names if all(w in n.lower() for w in words)]
    close = get_close_matches(given, names, n=3, cutoff=0.4)
    return list(dict.fromkeys(containing[:5] + close))[:5]


def _closest(request_type: str | None, neighborhood: str | None) -> dict:
    types, hoods = _known_names()
    out = {}
    if request_type and request_type not in types:
        out["request_type"] = _suggest(request_type, types)
    if neighborhood and neighborhood not in hoods:
        out["neighborhood"] = _suggest(neighborhood, hoods)
    return out


# ---------- the number check ----------

NUMBER = re.compile(
    # not inside a word or a longer number, nor the second half of 2025-03 or 3/4
    r"(?<![\w.$])(?<!\d[-/])(-?)(\$?)((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"(\s?(?:%|percent(?:age points?)?\b|points?\b|pp\b|million\b|[mM]\b|billion\b|bn\b|"
    r"thousand\b|[kK]\b))?"
)
CITATION = re.compile(r"\s*【[^】]*】")
SCALES = {"m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9, "k": 1e3, "thousand": 1e3}


def _numbers(text: str) -> list[tuple[str, float, int, str]]:
    """(text as written, value, decimals of precision, unit) for each number in text. Plain
    integers of 1,000 or more with trailing zeros are precise to their last nonzero digit, so
    16,000 can round 15,909; smaller ones (10, $20M) must match exactly."""
    found = []
    for match in NUMBER.finditer(text):
        _, dollar, digits, unit = match.groups()
        unit = (unit or "").strip().lower()
        # percentage points compare like percentages: tools give rate changes as fractions
        unit = "%" if unit in ("%", "percent", "pp") or "point" in unit else unit
        plain = digits.replace(",", "")
        if "." in plain:
            decimals = len(plain.split(".")[1])
        elif float(plain) >= 1000 and not unit:
            decimals = -(len(plain) - len(plain.rstrip("0")))
        else:
            decimals = 0
        found.append((match.group(0).strip(), float(plain), decimals, unit or dollar))
    return found


def _is_year(value: float, decimals: int, unit: str, written: str) -> bool:
    """Years, and 311 as the service's name: bare integers that aren't quantities."""
    bare = not unit and decimals <= 0 and "," not in written
    return bare and (1900 <= value <= 2100 or value == 311)


def _collect(data, out: set[float]) -> None:
    if isinstance(data, bool) or data is None:
        return
    if isinstance(data, int | float):
        out.add(abs(float(data)))
    elif isinstance(data, dict):
        for v in data.values():
            _collect(v, out)
    elif isinstance(data, list):
        for v in data:
            _collect(v, out)


def known_values(tool_results: list[str], user_texts: list[str]) -> set[float]:
    """Every number in the tool results, and the user's numbers (percents also as fractions)."""
    values: set[float] = set()
    for result in tool_results:
        try:
            _collect(json.loads(result), values)
        except json.JSONDecodeError:
            continue
    for text in user_texts:
        for _, value, _, unit in _numbers(text):
            values |= {value, value / 100} if unit == "%" else {value * SCALES.get(unit, 1)}
    return values


def unverified_numbers(answer: str, known: set[float]) -> list[str]:
    """Numbers in the answer that no known value rounds to, as written in the answer. Rates may
    be written as percentages of fractions; money in millions or thousands. Years are skipped."""
    out = []
    for written, value, decimals, unit in _numbers(answer):
        if _is_year(value, decimals, unit, written) or written in out:
            continue
        # tools give rates as fractions, and known_values stores the user's percents as fractions
        scale = 0.01 if unit == "%" else SCALES.get(unit, 1.0)
        tolerance = 10.0 ** -(decimals + 3) if decimals > 0 else 1e-6
        if not any(
            math.isclose(round(k / scale, decimals), value, abs_tol=tolerance) for k in known
        ):
            out.append(written)
    return out


# ---------- the agent ----------


@wrap_model_call
def retry_bad_tool_call(request, handler):
    """gpt-oss on Groq sometimes misnames a tool and Groq rejects the reply with a 400; ask
    again with a hint naming the tools (a plain retry tends to repeat the mistake)."""
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


SCENARIO_WORDS = {
    "base": "base",
    "hold_flat": "hold-flat baseline",
    "demand_plus_20": "demand +20%",
    "demand_minus_20": "demand -20%",
    "snowstorm": "snowstorm",
    "heat_wave": "heat wave",
}


def _for(departments) -> str:
    if not departments:
        return "all departments"
    if isinstance(departments, str):
        departments = [departments]
    return ", ".join(NAMES.get(d, str(d)) for d in departments)


def _summary(name: str, args: dict) -> str:
    """Plain words for a trace step. args are the model's raw arguments, so anything odd falls
    back to naming the tool rather than failing the request."""
    try:
        return _describe(name, args)
    except (TypeError, ValueError, AttributeError):
        return f"Called {name}"


def _describe(name: str, args: dict) -> str:
    if name == "get_plan":
        scenario = SCENARIO_WORDS.get(args.get("scenario", "base"), args.get("scenario"))
        return f"Read the {scenario} plan for {_for(args.get('departments'))}"
    if name == "run_what_if":
        parts = []
        multiplier = args.get("demand_multiplier", 1.0)
        if multiplier != 1.0:
            parts.append(f"demand {round((multiplier - 1) * 100):+d}%")
        if args.get("shock", "none") != "none":
            parts.append(f"a {args['shock'].replace('_', ' ')}")
        if args.get("on_time_target", 0.9) != 0.9:
            parts.append(f"a {round(args['on_time_target'] * 100)}% on-time target")
        return "Re-ran the plan with " + (" and ".join(parts) or "the base settings")
    if name == "get_forecast":
        return f"Read the 2025 forecast for {_for(args.get('departments'))}"
    metric = str(args.get("metric", "")).replace("_", " ")
    group = str(args.get("group_by", "")).replace("_", " ")
    where = _for(args.get("departments"))
    return f"Looked up {metric} by {group} for {where}, {args.get('year', 2024)}"


def _what_if(calls: list[dict]) -> SolveRequest | None:
    for c in reversed(calls):
        if c["name"] == "run_what_if":
            try:
                return SolveRequest(**{k: v for k, v in c["args"].items() if k != "departments"})
            except ValidationError:
                continue
    return None


def run_ask_with_stats(messages: list[ChatMessage]) -> tuple[AskResponse, dict]:
    agent = create_agent(
        llm.chat_model(),
        TOOLS,
        system_prompt=AGENT_PROMPT,
        middleware=[
            ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS, exit_behavior="end"),
            retry_bad_tool_call,
        ],
    )
    history = to_langchain(messages)
    result = agent.invoke({"messages": history})
    new = result["messages"][len(history) :]
    results = [m for m in new if isinstance(m, ToolMessage)]
    # past the cap the limiter answers the blocked calls with errors and ends the run with its
    # own AIMessage, so only calls that returned a result go in the trace
    # a tool that returned {"error": ...} didn't run either, so it stays out of the trace
    ran = {
        m.tool_call_id
        for m in results
        if m.status == "success" and not m.content.startswith('{"error"')
    }
    capped = any(m.status == "error" and m.content.startswith(LIMIT_ERRORS) for m in results)
    ai = [m for m in new if isinstance(m, AIMessage)][: -1 if capped else None]
    calls = [c for m in ai for c in m.tool_calls if c["id"] in ran and c["name"] in TOOL_NAMES]
    final = ai[-1] if ai and not ai[-1].tool_calls and not capped else None
    # gpt-oss sometimes appends citation marks like 【run_what_if†result】; drop them
    answer = CITATION.sub("", final.text).strip() if final else ""
    tool_results = [m.content for m in results if m.status == "success"]
    user_texts = [m.content for m in messages if m.role == "user"]
    unverified = unverified_numbers(answer, known_values(tool_results, user_texts))
    if not answer:  # the server's own message, so there is nothing to check
        answer = (
            f"I couldn't finish within {MAX_TOOL_CALLS} tool calls. Try a narrower question, "
            "for example one department or one scenario."
        )
    response = AskResponse(
        answer=answer,
        trace=[
            ToolTraceStep(tool=c["name"], args=c["args"], summary=_summary(c["name"], c["args"]))
            for c in calls
        ],
        what_if=_what_if(calls),
        unverified_numbers=unverified,
    )
    stats = {
        "tool_calls": len(calls),
        "llm_calls": len(ai),
        "uncached_tokens": llm.uncached_tokens(ai),
        "numbers": len(
            {n[0] for n in _numbers(answer if final else "") if not _is_year(*n[1:], n[0])}
        ),
        "unverified": len(unverified),
    }
    return response, stats


def run_ask(messages: list[ChatMessage]) -> AskResponse:
    """Answer a planning question from tool results, flagging numbers no tool returned."""
    return run_ask_with_stats(messages)[0]
