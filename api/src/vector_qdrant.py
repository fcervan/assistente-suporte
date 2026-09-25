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


def upsert(chunks: list[dict]) -> int:
    """chunks: [{texto, fonte, pagina}]. Retorna qtd inserida."""
    if not chunks:
        return 0
    vecs = embeddings.embed([c["texto"] for c in chunks])
    garantir_colecao(dim=len(vecs[0]))
    pts = [
        PointStruct(id=str(uuid.uuid4()), vector=v,
                    payload={"texto": c["texto"], "fonte": c.get("fonte", ""),
                             "pagina": c.get("pagina")})
        for c, v in zip(chunks, vecs)
    ]
    client().upsert(collection_name=config.QDRANT_COLLECTION, points=pts)
    return len(pts)


def buscar(query: str, top_k: int = 8) -> list[dict]:
    """Busca densa + re-rank BM25 local (híbrido leve sem sparse server)."""
    qv = embeddings.embed_query(query)
    hits = client().query_points(
        collection_name=config.QDRANT_COLLECTION, query=qv, limit=top_k
    ).points
    densos = [{"texto": h.payload.get("texto", ""), "fonte": h.payload.get("fonte", ""),
               "pagina": h.payload.get("pagina"), "dense": round(float(h.score), 4)}
              for h in hits]
    if not densos:
        return []
    lex = embeddings.busca_bm25(query, densos, top_k=top_k)
    return embeddings.fusao_rrf(densos, lex)[:top_k]
