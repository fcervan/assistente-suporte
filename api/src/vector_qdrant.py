"""Qdrant: coleção suporte_ti (denso + payload fonte/pagina)."""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from . import config, embeddings


def client() -> QdrantClient:
    return QdrantClient(url=config.QDRANT_URL)


def garantir_colecao(dim: int = 384) -> None:
    cli = client()
    if not cli.collection_exists(config.QDRANT_COLLECTION):
        cli.create_collection(
            collection_name=config.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def wipe_colecao() -> None:
    """Apaga a coleção inteira (Fase 4: base antiga é lixo, reimporta do zero)."""
    cli = client()
    if cli.collection_exists(config.QDRANT_COLLECTION):
        cli.delete_collection(collection_name=config.QDRANT_COLLECTION)


def upsert(chunks: list[dict]) -> int:
    """chunks: [{texto, fonte, pagina?, secao?, chunk_index?, doc_id?}]."""
    if not chunks:
        return 0
    vecs = embeddings.embed([c["texto"] for c in chunks])
    garantir_colecao(dim=len(vecs[0]))
    pts = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=v,
            payload={
                "texto": c["texto"],
                "fonte": c.get("fonte", ""),
                "pagina": c.get("pagina"),
                "secao": c.get("secao", ""),
                "chunk_index": c.get("chunk_index"),
                "doc_id": c.get("doc_id", ""),
                "versao_chunk": c.get("versao_chunk", config.VERSAO_CHUNK),
            },
        )
        for c, v in zip(chunks, vecs)
    ]
    client().upsert(collection_name=config.QDRANT_COLLECTION, points=pts)
    return len(pts)


def buscar(query: str, top_k: int = 8) -> list[dict]:
    """Busca densa ampla + re-rank BM25 local (híbrido leve sem sparse server)."""
    qv = embeddings.embed_query(query)
    pool = max(top_k * 5, 30)  # recall largo p/ o RRF escolher
    hits = (
        client().query_points(collection_name=config.QDRANT_COLLECTION, query=qv, limit=pool).points
    )
    densos = [
        {
            "texto": h.payload.get("texto", ""),
            "fonte": h.payload.get("fonte", ""),
            "pagina": h.payload.get("pagina"),
            "secao": h.payload.get("secao", ""),
            "dense": round(float(h.score), 4),
        }
        for h in hits
    ]
    if not densos:
        return []
    lex = embeddings.busca_bm25(query, densos, top_k=top_k)
    return embeddings.fusao_rrf(densos, lex)[:top_k]
