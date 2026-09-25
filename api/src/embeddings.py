"""Embeddings multilíngues PT + BM25 híbrido (RRF)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

from . import config


@lru_cache(maxsize=1)
def modelo():
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=config.EMBED_MODEL)


def embed(textos: list[str]) -> list[list[float]]:
    return modelo().embed_documents(textos)


def embed_query(texto: str) -> list[float]:
    return modelo().embed_query(texto)


def _tok(s: str) -> list[str]:
    return (s or "").lower().split()


def fusao_rrf(r_dense: list[dict], r_bm25: list[dict], k: int = 60,
              w_dense: float = 0.7, w_bm25: float = 0.3) -> list[dict]:
    """Reciprocal Rank Fusion entre ranking denso e léxico."""
    pos_d = {id(r): i for i, r in enumerate(r_dense)}
    pos_b = {id(r): i for i, r in enumerate(r_bm25)}
    todos = {id(r): r for r in r_dense + r_bm25}
    scored = []
    for rid, r in todos.items():
        s = 0.0
        if rid in pos_d:
            s += w_dense / (k + pos_d[rid] + 1)
        if rid in pos_b:
            s += w_bm25 / (k + pos_b[rid] + 1)
        scored.append({**r, "score": round(s, 6)})
    return sorted(scored, key=lambda x: x["score"], reverse=True)


def busca_bm25(query: str, docs: list[dict], top_k: int = 5) -> list[dict]:
    """docs: [{texto, fonte, ...}]. Retorna top_k com score bm25 normalizado."""
    if not docs:
        return []
    corpus = [_tok(d.get("texto", "")) for d in docs]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tok(query))
    mx = float(np.max(scores)) if len(scores) else 0.0
    idx = list(np.argsort(scores)[::-1][:top_k])
    return [{**docs[i], "bm25": round(float(scores[i]) / mx if mx else 0.0, 4)} for i in idx]
