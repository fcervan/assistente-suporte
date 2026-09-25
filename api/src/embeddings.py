"""Embeddings multilíngues PT + BM25 híbrido (RRF)."""

from __future__ import annotations

import re
import unicodedata
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


def _stemmer():
    try:
        from functools import lru_cache

        from nltk.stem.snowball import SnowballStemmer

        @lru_cache(maxsize=1)
        def _get():
            return SnowballStemmer("portuguese")

        return _get()
    except Exception:
        return None


def _tok(s: str) -> list[str]:
    """Normaliza (minúsculas, sem acento/pontuação) + stemming PT p/ BM25
    casar variações ('pedidos'/'pedido', 'enviar'/'envio')."""
    base = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    toks = re.findall(r"[a-z0-9]+", base.lower())
    stem = _stemmer()
    if stem is None:
        return toks
    try:
        return [stem.stem(t) for t in toks]
    except Exception:
        return toks


# Glossário SmartLabel p/ expansão de query no BM25 (chaves já normalizadas,
# sem acento): a pergunta usa "pedido/request", o manual usa
# "encomenda/volume/transmissão/requisição". Grupos restritos ao domínio p/
# não puxar o falso-amigo "mais de um documento fiscal por pedido" (§4.2).
SINONIMOS = {
    "pedido": ["encomenda", "volume", "lote"],
    "pedidos": ["encomenda", "encomendas", "volume", "volumes", "lote"],
    "encomenda": ["pedido", "volume"],
    "encomendas": ["pedido", "pedidos", "volume", "volumes"],
    "volume": ["pedido", "encomenda"],
    "volumes": ["pedido", "pedidos", "encomenda", "encomendas"],
    "request": ["requisicao", "transmissao", "solicitacao"],
    "requests": ["requisicao", "transmissao"],
    "requisicao": ["request", "transmissao"],
    "requisicoes": ["request", "transmissao"],
    "transmissao": ["request", "requisicao"],
    "transmissoes": ["request", "requisicao"],
    "lote": ["encomendas", "volumes"],
}


def expandir_query(query: str) -> str:
    """Query original + sinônimos do domínio p/ o BM25 casar pergunta↔manual
    ('pedido por request' casa 'volumes (encomendas)' e 'transmissão')."""
    base = unicodedata.normalize("NFKD", query or "").encode("ascii", "ignore").decode()
    palavras = re.findall(r"[a-z0-9]+", base.lower())
    extras = [s for p in palavras for s in SINONIMOS.get(p, [])]
    return f"{query} {' '.join(extras)}".strip() if extras else (query or "")


def _chave(r: dict) -> tuple:
    return (r.get("texto", ""), r.get("secao", ""), r.get("pagina"), r.get("fonte", ""))


def fusao_rrf(
    r_dense: list[dict], r_bm25: list[dict], k: int = 60, w_dense: float = 0.5, w_bm25: float = 0.5
) -> list[dict]:
    """Reciprocal Rank Fusion com pesos iguais (padrão RRF).

    Fusão por CONTEÚDO (texto/secao/pagina/fonte), não por id(): o BM25
    devolve cópias dos dicts densos, e fundir por id() jamais somaria os
    dois sinais no mesmo documento (bug que anulava o híbrido).
    Pesos iguais permitem que um literal exato (BM25 #1, ex: 'clienteCodigo',
    'Response 200') supere um semanticamente próximo mas sem o termo.
    """
    pos_d = {_chave(r): i for i, r in enumerate(r_dense)}
    pos_b = {_chave(r): i for i, r in enumerate(r_bm25)}
    todos = {_chave(r): r for r in r_dense + r_bm25}
    scored = []
    for chave, r in todos.items():
        s = 0.0
        if chave in pos_d:
            s += w_dense / (k + pos_d[chave] + 1)
        if chave in pos_b:
            s += w_bm25 / (k + pos_b[chave] + 1)
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
