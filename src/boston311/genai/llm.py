"""Chat model from LLM_MODEL / LLM_PROVIDER, at temperature 0, with every call cached to disk."""

import os
from functools import cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from langchain_core.messages import AIMessage, BaseMessage

from boston311.config import CACHE_DIR, DEFAULT_LLM_MODEL


class CountingCache(SQLiteCache):
    """SQLite cache that counts misses: update() only runs after a real model call."""

    misses = 0

    def update(self, prompt, llm_string, return_val):
        self.misses += 1
        super().update(prompt, llm_string, return_val)


@cache
def enable_cache() -> CountingCache:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    disk_cache = CountingCache(str(CACHE_DIR / "llm.sqlite"))
    set_llm_cache(disk_cache)
    return disk_cache


def model_name() -> str:
    return os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL)


def chat_model(model: str | None = None):
    enable_cache()
    provider = os.environ.get("LLM_PROVIDER", "groq")
    extra: dict[str, Any] = {"reasoning_effort": "low"} if provider == "groq" else {}
    return init_chat_model(model or model_name(), model_provider=provider, temperature=0, **extra)


def structured(model, schema):
    """Strict JSON-schema output; returns {"raw", "parsed", "parsing_error"}."""
    return model.with_structured_output(schema, method="json_schema", strict=True, include_raw=True)


def uncached_tokens(messages: list[BaseMessage]) -> int:
    """Tokens that count against Groq's rate limits: prompt-cache reads are free."""
    total = 0
    for m in messages:
        usage = getattr(m, "usage_metadata", None) if isinstance(m, AIMessage) else None
        if usage:
            cached = (usage.get("input_token_details") or {}).get("cache_read") or 0
            total += usage["input_tokens"] - cached + usage["output_tokens"]
    return total
