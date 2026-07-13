"""Mini knowledge-base search. Deterministic jaccard overlap, no embeddings.

Provenance-aware: when defense is on, UGC entries get a score penalty so
attacker-published listings can't outrank legit FAQ entries.
"""
from __future__ import annotations
import re
from typing import List

from .store import store
from .config import defenses


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _score(query_tokens: set[str], doc_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


def _candidates() -> List[dict]:
    """Mix FAQ entries and UGC listings into one searchable corpus."""
    out: List[dict] = []
    for kb in store.kb_entries.values():
        out.append({
            "id": f"kb#{kb.id}",
            "title": kb.title,
            "description": kb.description,
            "source": "faq",
        })
    for l in store.listings.values():
        out.append({
            "id": f"listing#{l.id}",
            "title": l.title,
            "description": l.description,
            "source": "ugc",
        })
    return out


def search(query: str) -> dict:
    """Return top match and top-3 candidates with scores."""
    q = _tokens(query)
    scored = []
    for c in _candidates():
        doc = _tokens(c["title"] + " " + c["description"])
        s = _score(q, doc)
        if defenses.rerank_kb_by_provenance and c["source"] == "ugc":
            s -= 0.5
        scored.append({**c, "score": round(s, 3)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[0] if scored and scored[0]["score"] > 0 else None
    return {"top_match": top, "candidates": scored[:3]}
