"""Nearest request types for a short problem description, over the knowledge base."""

import threading
from functools import cache

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from boston311.config import CACHE_DIR
from boston311.genai.kb import KB_PATH, load_kb

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
INDEX_PATH = CACHE_DIR / "kb_index.json"
_INDEX_LOCK = threading.Lock()  # first requests may arrive together; build and write once
DOCS_PER_TYPE_SEARCH = 4  # fetch k x this many docs, then keep the first k distinct types


def _embeddings():
    from langchain_community.embeddings import FastEmbedEmbeddings

    return FastEmbedEmbeddings(model_name=EMBEDDING_MODEL, cache_dir=str(CACHE_DIR / "fastembed"))


@cache
def _store() -> InMemoryVectorStore:
    # embedding ~790 texts takes ~15 s on CPU, so keep the vectors until the KB file changes
    with _INDEX_LOCK:
        if INDEX_PATH.exists() and INDEX_PATH.stat().st_mtime >= KB_PATH.stat().st_mtime:
            return InMemoryVectorStore.load(str(INDEX_PATH), _embeddings())
        docs = []
        for entry in load_kb():
            meta = {"request_type": entry["request_type"], "description": entry["description"]}
            docs.append(Document(f"{entry['request_type']}: {entry['description']}", metadata=meta))
            docs += [Document(p, metadata=meta) for p in entry["phrasings"]]
        store = InMemoryVectorStore.from_documents(docs, _embeddings())
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        store.dump(str(INDEX_PATH))
        return store


def search(query: str, k: int = 5) -> list[dict]:
    """Up to k distinct request types, closest first, each with its one-line description."""
    found: dict[str, dict] = {}
    for doc in _store().similarity_search(query, k=k * DOCS_PER_TYPE_SEARCH):
        found.setdefault(doc.metadata["request_type"], doc.metadata)
        if len(found) == k:
            break
    return list(found.values())
