"""Baseline intake: retrieve 5 candidate types, one strict structured call, look up the routing.

Also holds what the agent shares: the LLM draft shapes and the server-side fill."""

from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import AfterValidator, BaseModel, Field, create_model

from boston311.api.schemas import ChatMessage, IntakeResponse, RoutedRequest, ToolTraceStep
from boston311.genai import llm
from boston311.genai.kb import request_type_table
from boston311.genai.retriever import search

OUT_OF_SCOPE = "out_of_scope"

PIPELINE_PROMPT = """You route Boston 311 reports from residents. Only four departments are \
in scope: Public Works (streets, sidewalks, lights, trash, graffiti), Transportation (parking, \
signs, signals), Parks & Recreation (parks and trees), and Inspectional Services (housing and \
building conditions such as heat, pests and unsafe buildings).
Split the conversation into separate problems, one request per problem, and pick each \
problem's request type from the candidate list. Use "out_of_scope" for a problem none of the \
candidates fits or that belongs to another department.
If you cannot tell which candidate fits, return no request for that problem and ask one short \
follow-up question instead. Otherwise follow_up_question is null.
location is the place as the resident gave it, or null. details is one line for the crew.
reply is a short, friendly message to the resident saying what you filed or what you need."""


def draft_schema(allowed: list[str], enum: bool = True) -> type[BaseModel]:
    """The LLM's output shape; request_type can only be one of `allowed` or out_of_scope.

    enum=True puts the names in the JSON schema (strict output, few names). enum=False checks
    them in a validator instead, so a long list isn't resent with every agent call.
    """
    names = (*allowed, OUT_OF_SCOPE)

    def known(value: str) -> str:
        if value not in names:
            raise ValueError(f"{value!r} is not a request type: use an exact name or out_of_scope")
        return value

    request = create_model(
        "DraftRequest",
        request_type=(Literal[names] if enum else Annotated[str, AfterValidator(known)], ...),
        location=(str | None, Field(..., description="The place as the resident gave it")),
        details=(str, Field(..., description="One line for the crew")),
    )
    return create_model(
        "IntakeDraft",
        requests=(list[request], Field(..., description="One entry per problem")),
        follow_up_question=(str | None, ...),
        reply=(str, ...),
    )


def to_langchain(messages: list[ChatMessage]) -> list:
    return [HumanMessage(m.content) if m.role == "user" else AIMessage(m.content) for m in messages]


# words the model sometimes writes instead of leaving follow_up_question empty
NO_QUESTION = {"", "null", "none", "n/a", "na"}


def _question(text: str | None) -> str | None:
    """The follow-up question, or None when the model wrote "null" or the like as text."""
    if text is None or text.strip().lower() in NO_QUESTION:
        return None
    return text.strip()


def to_response(draft, trace: list[ToolTraceStep], fallback_used: bool = False) -> IntakeResponse:
    """Department, queue and typical days come from the lookup table, never from the model."""
    table = request_type_table()
    routed = []
    for r in draft.requests:
        if r.request_type == OUT_OF_SCOPE:
            continue
        row = table.loc[r.request_type]
        days = row["median_days_to_close"]
        routed.append(
            RoutedRequest(
                request_type=r.request_type,
                department=row["department"],
                queue=row["queue"],
                location=r.location,
                details=r.details,
                typical_days_to_close=None if days != days else float(days),  # NaN: none closed
            )
        )
    question = _question(draft.follow_up_question)
    return IntakeResponse(
        requests=routed,
        follow_up_question=question,
        out_of_scope=not routed and question is None,
        reply=draft.reply,
        trace=trace,
        fallback_used=fallback_used,
    )


def run_pipeline(messages: list[ChatMessage]) -> tuple[IntakeResponse, dict]:
    query = " ".join(m.content for m in messages if m.role == "user")
    candidates = search(query)
    listing = "\n".join(f"- {c['request_type']}: {c['description']}" for c in candidates)
    prompt = [
        SystemMessage(PIPELINE_PROMPT),
        *to_langchain(messages),
        HumanMessage(f"Candidate request types:\n{listing}"),
    ]
    schema = draft_schema([c["request_type"] for c in candidates])
    reply = llm.structured(llm.chat_model(), schema).invoke(prompt)
    if reply["parsed"] is None:
        raise ValueError(f"pipeline output did not validate: {reply['parsing_error']}")
    trace = [
        ToolTraceStep(
            tool="search_request_types",
            args={"queries": [query]},
            summary=f"Matched {len(candidates)} candidate request types",
        )
    ]
    stats = {
        "tool_calls": 0,
        "llm_calls": 1,
        "uncached_tokens": llm.uncached_tokens([reply["raw"]]),
    }
    return to_response(reply["parsed"], trace), stats
