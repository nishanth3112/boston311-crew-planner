"""Build data/processed/request_type_kb.json; LLM calls are disk-cached, so reruns are free."""

import json

import pandas as pd

from boston311.config import INTERIM_DIR
from boston311.genai import kb, llm

types = pd.read_csv(kb.REQUEST_TYPES_PATH)
df = pd.read_parquet(INTERIM_DIR / "clean_2024.parquet", columns=["request_type", "case_title"])
titles = {
    t: [title for title in group.value_counts().index if title != t][:5]
    for t, group in df.groupby("request_type")["case_title"]
}
entries = kb.build_kb(types, titles, llm.chat_model())
kb.KB_PATH.write_text(json.dumps({"model": llm.model_name(), "types": entries}, indent=1) + "\n")
print(f"{len(entries)} request types, model {llm.model_name()}")
print(f"LLM calls (cache misses): {llm.enable_cache().misses}")
