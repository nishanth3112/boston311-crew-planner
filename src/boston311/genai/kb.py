"""The request-type knowledge base: an LLM-written description, resident phrasings and crew
needs per type, built offline once (calls are disk-cached) and read by the retriever."""

import json
from functools import cache
from typing import Literal

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, create_model

from boston311.config import DEPARTMENTS, PROCESSED_DIR
from boston311.genai import llm

KB_PATH = PROCESSED_DIR / "request_type_kb.json"
REQUEST_TYPES_PATH = PROCESSED_DIR / "request_types.csv"
BATCH_SIZE = 20
ROUNDS = 3  # re-ask for types a batch skipped, at most this many times

KB_PROMPT = """You are writing a knowledge base for Boston's 311 service-request intake.
For every request type listed, return:
- description: one plain-English line saying what problems this request type covers.
- phrasings: exactly 4 short messages a Boston resident might type when reporting it, \
in varied everyday wording. No street addresses or names.
- crew_needs: one line on what the crew needs from the resident (exact location, size, \
a photo, a license plate, ...).
Use the department, queue and example case titles to work out what cryptic type names mean.
Types marked "staff only" were never reported by residents in 2024: they are internal work \
orders that city crews log. Say so in the description, and write the phrasings as a crew \
member would log the job.
Return every listed request type exactly once."""


@cache
def request_type_table() -> pd.DataFrame:
    """request_types.csv indexed by request_type: department, queue, median_days_to_close."""
    return pd.read_csv(REQUEST_TYPES_PATH).set_index("request_type")


@cache
def load_kb() -> list[dict]:
    return json.loads(KB_PATH.read_text())["types"]


def _batch_schema(types: list[str]) -> type[BaseModel]:
    entry = create_model(
        "RequestTypeEntry",
        request_type=(Literal[tuple(types)], ...),
        description=(str, ...),
        phrasings=(list[str], ...),
        crew_needs=(str, ...),
    )
    return create_model("RequestTypeBatch", types=(list[entry], ...))


def _describe(row, titles: list[str], staff_only: bool) -> str:
    line = f"- {row.request_type} (department: {DEPARTMENTS[row.department]['name']}, "
    line += f"queue: {row.queue}{', staff only' if staff_only else ''})"
    if titles:
        line += ". Example case titles: " + "; ".join(titles)
    return line


def build_kb(
    types: pd.DataFrame,
    titles: dict[str, list[str]],
    model,
    staff_only: frozenset[str] = frozenset(),
) -> list[dict]:
    """One entry per row of `types`, sorted by request_type; raises if a type never comes back."""
    entries: dict[str, dict] = {}
    for _ in range(ROUNDS):
        pending = types[~types["request_type"].isin(entries)]
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending.iloc[start : start + BATCH_SIZE]
            names = list(batch["request_type"])
            listing = "\n".join(
                _describe(r, titles.get(r.request_type, []), r.request_type in staff_only)
                for r in batch.itertuples()
            )
            reply = llm.structured(model, _batch_schema(names)).invoke(
                [SystemMessage(KB_PROMPT), HumanMessage(listing)]
            )
            if reply["parsed"] is None:
                raise ValueError(f"unparseable knowledge-base batch: {reply['parsing_error']}")
            for entry in reply["parsed"].types:
                entries.setdefault(entry.request_type, entry.model_dump())
    if missing := sorted(set(types["request_type"]) - set(entries)):
        raise ValueError(f"no knowledge-base entry for {missing}")
    return [entries[t] for t in sorted(entries)]
