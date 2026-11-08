"""Pipeline vs agent on a labeled intake set.

    uv run python -m boston311.eval.intake_eval data/processed/intake_dev_set.csv

The CSV needs columns id, message, expected_request_types and expects_follow_up (0/1).
expected_request_types separates problems with ";" and accepted alternatives for one problem
with "|"; it is empty when the message is out of scope. A problem is right if a prediction
matches any of its alternatives; department and queue come from the lookup table, as in the
app. Messages that expect a follow-up are scored on the follow-up only. A path that raises on
a message counts as an error for that message.
Agent cost excludes calls Groq rejected (retried) and a failed agent run before a
fallback, whose message reports the pipeline's cost; real usage is somewhat higher.
"""

import sys

import pandas as pd

from boston311.api.schemas import ChatMessage
from boston311.genai import llm
from boston311.genai.intake_agent import run_intake_with_stats
from boston311.genai.intake_pipeline import run_pipeline
from boston311.genai.kb import request_type_table

PATHS = {"pipeline": run_pipeline, "agent": run_intake_with_stats}


def parse_problems(cell: str) -> list[list[str]]:
    """ "A ; B|C" -> [["A"], ["B", "C"]]: one list of accepted types per problem."""
    problems = [[t.strip() for t in p.split("|") if t.strip()] for p in cell.split(";")]
    return [p for p in problems if p]


def matched(problems: list[list[str]], predicted: list[str], key) -> int:
    """Problems matched by distinct predictions (compared through key). Problems with the fewest
    alternatives go first, so a prediction several problems accept isn't spent on the wrong one."""
    left = [key(p) for p in predicted]
    hits = 0
    for alternatives in sorted(problems, key=len):
        accepted = {key(a) for a in alternatives}
        hit = next((i for i, p in enumerate(left) if p in accepted), None)
        if hit is not None:
            del left[hit]
            hits += 1
    return hits


def run_path(run, dev: pd.DataFrame) -> list[dict]:
    records = []
    for row in dev.itertuples():
        record = {
            "id": row.id,
            "problems": parse_problems(row.expected_request_types),
            "follow_up_expected": bool(int(row.expects_follow_up)),
        }
        try:
            response, stats = run([ChatMessage(role="user", content=row.message)])
            record |= stats | {
                "predicted": [r.request_type for r in response.requests],
                "asked": response.follow_up_question is not None,
                "out_of_scope": response.out_of_scope,
                "fallback": response.fallback_used,
            }
        except Exception as error:  # counted and printed, so one bad message doesn't stop the run
            record["error"] = f"{type(error).__name__}: {error}"[:120]
        records.append(record)
    return records


def summarize(records: list[dict]) -> dict:
    table = request_type_table()
    ok = [r for r in records if "error" not in r]
    scored = [r for r in ok if not r["follow_up_expected"]]
    multi = [r for r in scored if len(r["problems"]) > 1]
    oos = [r for r in scored if not r["problems"]]
    asked = [r for r in ok if r["asked"]]
    wanted = [r for r in ok if r["follow_up_expected"]]
    expected = sum(len(r["problems"]) for r in scored)

    def correct(key=lambda t: t):
        return f"{sum(matched(r['problems'], r['predicted'], key) for r in scored)}/{expected}"

    def avg(key):
        return round(sum(r[key] for r in ok) / len(ok), 1) if ok else 0

    return {
        "messages": len(records),
        "errors": len(records) - len(ok),
        "type correct": correct(),
        "department correct": correct(table["department"].get),
        "queue correct": correct(table["queue"].get),
        "split correct": f"{sum(len(r['predicted']) == len(r['problems']) for r in multi)}"
        f"/{len(multi)}",
        "follow-up precision": f"{sum(r['follow_up_expected'] for r in asked)}/{len(asked)}",
        "follow-up recall": f"{sum(r['asked'] for r in wanted)}/{len(wanted)}",
        "out of scope correct": f"{sum(r['out_of_scope'] for r in oos)}/{len(oos)}",
        "tool calls / msg": avg("tool_calls"),
        "LLM calls / msg": avg("llm_calls"),
        "uncached tokens / msg": avg("uncached_tokens"),
        "fallbacks": sum(r.get("fallback", False) for r in ok),
    }


def markdown(rows: list[dict]) -> str:
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
    return "\n".join(lines + ["| " + " | ".join(map(str, r.values())) + " |" for r in rows])


def label(r: dict, types: list[str]) -> str:
    if types:
        return " / ".join(types)
    return "(follow-up)" if r.get("asked", r["follow_up_expected"]) else "(none)"


def main(path: str) -> None:
    dev = pd.read_csv(path, keep_default_na=False)
    results = {name: run_path(run, dev) for name, run in PATHS.items()}
    print(f"Intake eval on `{path}`, model `{llm.model_name()}`\n")
    print(markdown([{"path": name} | summarize(records) for name, records in results.items()]))
    print("\nPer message\n")
    detail = [
        {
            "id": r["id"],
            "path": name,
            "expected": label(
                {"follow_up_expected": r["follow_up_expected"]},
                [" or ".join(alternatives) for alternatives in r["problems"]],
            ),
            "got": r.get("error") or label(r, r["predicted"]),
        }
        for name, records in results.items()
        for r in records
    ]
    print(markdown(detail))


if __name__ == "__main__":
    main(sys.argv[1])
