"""Planning analyst agent on a labeled question set.

    uv run python -m boston311.eval.analyst_eval data/processed/analyst_dev_set.csv

The CSV needs these columns:
- id, question
- expected_tools: tools the answer needs, separated by ";". "|" separates tools that can stand
  in for each other: "get_plan|run_what_if;get_forecast" needs get_plan or run_what_if, and
  get_forecast.
- expected_arguments: a JSON object {tool: {argument: value}}. A value matches when the agent
  passed the same value to that tool in any of its calls: numbers to 1e-6, text ignoring case,
  lists as sets. An argument of a tool whose stand-in was called instead isn't scored. Use {}
  for none.
- expected_facts: what a correct answer says, for a person to check against the printed answers.

The whole file is checked before any LLM call. Errors name rows, never their content.
"""

import json
import sys
import time

import pandas as pd
from groq import RateLimitError

from boston311.api.schemas import ChatMessage
from boston311.genai import llm
from boston311.genai.analyst_agent import TOOLS, run_ask_with_stats

RATE_LIMIT_WAIT = 60  # seconds; Groq limits tokens per minute
COLUMNS = ["id", "question", "expected_tools", "expected_arguments", "expected_facts"]
TOOL_ARGS = {t.name: t.args for t in TOOLS}  # argument name -> JSON schema
# an argument the model leaves out takes the tool's default, so score against that
DEFAULTS = {
    tool: {name: spec["default"] for name, spec in args.items() if "default" in spec}
    for tool, args in TOOL_ARGS.items()
}


def _allowed(spec: dict) -> list | None:
    """The values a schema allows (for lists, per item), or None when it's open."""
    for option in [spec, *spec.get("anyOf", [])]:
        if "enum" in option:
            return option["enum"]
        if "enum" in option.get("items", {}):
            return option["items"]["enum"]
    return None


def _valid(tool: str, name: str, value) -> bool:
    if name not in TOOL_ARGS[tool]:
        return False
    allowed = _allowed(TOOL_ARGS[tool][name])
    values = value if isinstance(value, list) else [value]
    return allowed is None or all(v in allowed for v in values)


def parse_tools(cell: str) -> list[list[str]]:
    """ "a|b;c" -> [["a", "b"], ["c"]]: one list of stand-ins per tool the answer needs."""
    groups = [[t.strip() for t in g.split("|") if t.strip()] for g in cell.split(";")]
    return [g for g in groups if g]


def load_set(path) -> pd.DataFrame:
    df = pd.read_csv(path, keep_default_na=False, dtype=str)
    if missing := [c for c in COLUMNS if c not in df.columns]:
        raise ValueError(f"{path}: missing columns {missing}")
    problems = [f"row {i}: duplicate id" for i in df["id"][df["id"].duplicated()]]
    for row in df.itertuples():
        tools = {t for g in parse_tools(row.expected_tools) for t in g}
        if not tools or tools - set(TOOL_ARGS):
            problems.append(f"row {row.id}: expected_tools must name only the four tools")
            continue
        try:
            arguments = json.loads(row.expected_arguments or "{}")
        except json.JSONDecodeError:
            problems.append(f"row {row.id}: expected_arguments is not valid JSON")
            continue
        for tool, args in arguments.items() if isinstance(arguments, dict) else [(None, None)]:
            if (
                tool not in tools
                or not isinstance(args, dict)
                or not all(_valid(tool, name, value) for name, value in args.items())
            ):
                problems.append(
                    f"row {row.id}: expected_arguments must map expected tools to valid arguments"
                )
                break
    if problems:
        raise ValueError(f"{path} has {len(problems)} problem(s):\n" + "\n".join(problems))
    return df


def same(expected, actual) -> bool:
    if isinstance(expected, list):
        return isinstance(actual, list) and {str(v).lower() for v in expected} == {
            str(v).lower() for v in actual
        }
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        return isinstance(actual, int | float) and abs(expected - actual) < 1e-6
    return str(expected).lower() == str(actual).lower()


def score(row, response) -> dict:
    """Tool choice, and argument matches out of the arguments scored, for one question.

    In each group of stand-ins, only the called tool that matches best is scored (the first
    expected one when none was called). An expected argument matches if any call of its tool
    passed that value, with left-out arguments at the tool's default.
    """
    called = {}
    for step in response.trace:
        called.setdefault(step.tool, []).append(DEFAULTS[step.tool] | step.args)
    expected = json.loads(row.expected_arguments or "{}")
    groups = parse_tools(row.expected_tools)

    def matches(tool):
        args = expected.get(tool, {})
        hits = sum(any(same(v, c.get(k)) for c in called.get(tool, [])) for k, v in args.items())
        return hits, len(args)

    hits = scored = 0
    for group in groups:
        candidates = [t for t in group if t in called] or group[:1]
        h, s = max((matches(t) for t in candidates), key=lambda m: (m[0], -m[1]))
        hits, scored = hits + h, scored + s
    return {
        "tools_ok": all(any(t in called for t in g) for g in groups),
        "args_hit": hits,
        "args_scored": scored,
    }


def ask(question: str):
    """One question; on Groq's per-minute rate limit, wait a minute and try once more."""
    messages = [ChatMessage(role="user", content=question)]
    try:
        return run_ask_with_stats(messages)
    except RateLimitError:
        time.sleep(RATE_LIMIT_WAIT)
        return run_ask_with_stats(messages)


def run(questions: pd.DataFrame) -> list[dict]:
    records = []
    for row in questions.itertuples():
        record = {"id": row.id, "facts": row.expected_facts}
        try:
            response, stats = ask(row.question)
            record |= stats | score(row, response)
            record |= {
                "answer": response.answer,
                "tools": ", ".join(s.tool for s in response.trace) or "(none)",
                "unverified_list": ", ".join(response.unverified_numbers),
            }
        except Exception as error:  # counted and printed, so one bad question doesn't stop the run
            # the first line only: Groq's messages go on to name the account
            record["error"] = f"{type(error).__name__}: {str(error).splitlines()[0]}"[:80]
        records.append(record)
    return records


def summarize(records: list[dict]) -> dict:
    ok = [r for r in records if "error" not in r]
    numbers = sum(r["numbers"] for r in ok)

    def avg(key):
        return round(sum(r[key] for r in ok) / len(ok), 1) if ok else 0

    return {
        "questions": len(records),
        "errors": len(records) - len(ok),
        "right tools": f"{sum(r['tools_ok'] for r in ok)}/{len(ok)}",
        "right arguments": f"{sum(r['args_hit'] for r in ok)}/{sum(r['args_scored'] for r in ok)}",
        "numbers verified": f"{numbers - sum(r['unverified'] for r in ok)}/{numbers}",
        "tool calls / q": avg("tool_calls"),
        "max tool calls": max((r["tool_calls"] for r in ok), default=0),
        "LLM calls / q": avg("llm_calls"),
        "uncached tokens / q": avg("uncached_tokens"),
    }


def markdown(rows: list[dict]) -> str:
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
    cells = [
        " | ".join(str(v).replace("|", "/").replace("\n", " ") for v in r.values()) for r in rows
    ]
    return "\n".join(lines + [f"| {c} |" for c in cells])


def main(path: str) -> None:
    questions = load_set(path)
    records = run(questions)
    print(f"Analyst eval on `{path}`, model `{llm.model_name()}`\n")
    print(markdown([summarize(records)]))
    print("\nPer question\n")
    print(
        markdown(
            [
                {
                    "id": r["id"],
                    "tools": r.get("tools", ""),
                    "right tools": r.get("tools_ok", ""),
                    "arguments": f"{r.get('args_hit', 0)}/{r.get('args_scored', 0)}",
                    "unverified": r.get("unverified_list", ""),
                    "error": r.get("error", ""),
                }
                for r in records
            ]
        )
    )
    print("\nAnswers, to check against the expected facts\n")
    for r in records:
        print(f"**{r['id']}** expected: {r['facts']}\n\n> {r.get('answer', r.get('error'))}\n")


if __name__ == "__main__":
    main(sys.argv[1])
