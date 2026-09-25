"""Cobre embeddings/vector_qdrant com stubs das deps pesadas.

Lógica testada é 100% real (fusão, payload, pool, wipe); só o álgebra
linear (numpy), o BM25 e o cliente Qdrant são dublês.
"""

import sys
import types

import pytest


def _numpy_stub():
    np = types.ModuleType("numpy")

    def _arr(xs):
        return list(xs)

    np.array = _arr
    np.max = lambda xs: max(list(xs))  # noqa: E731

    def _argsort(xs):
        xs = list(xs)
        return sorted(range(len(xs)), key=lambda i: xs[i])

    np.argsort = _argsort
    return np


def _bm25_stub():
    m = types.ModuleType("rank_bm25")

    class BM25Okapi:
        def __init__(self, corpus):
            self.corpus = corpus

        def get_scores(self, q):
            return [float(sum(1 for t in doc if t in q)) for doc in self.corpus]

    m.BM25Okapi = BM25Okapi
    return m


def _qdrant_stub(gravados, pontos):
    qc = types.ModuleType("qdrant_client")
    models = types.ModuleType("qdrant_client.models")

    class Distance:
        COSINE = "cosine"

    class VectorParams:
        def __init__(self, size, distance):
            self.size = size
            self.distance = distance

    class PointStruct:
        def __init__(self, id, vector, payload):
            self.id = id
            self.vector = vector
            self.payload = payload

    models.Distance = Distance
    models.VectorParams = VectorParams
    models.PointStruct = PointStruct

    class Client:
        def __init__(self, url=None):
            self.url = url
            self._pts = list(pontos)
            self.deleted = []

        def collection_exists(self, name):
            return True

        def create_collection(self, **k):
            pass

        def delete_collection(self, collection_name):
            self.deleted.append(collection_name)

        def upsert(self, collection_name, points):
            gravados.extend(points)

        def query_points(self, collection_name, query, limit):
            class R:
                pass

            r = R()
            r.points = self._pts[:limit]
            return r

    qc.QdrantClient = Client
    qc.models = models
    return qc, models, Client


@pytest.fixture()
def mods(monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", _numpy_stub())
    monkeypatch.setitem(sys.modules, "rank_bm25", _bm25_stub())
    for m in ("src.embeddings", "src.vector_qdrant", "qdrant_client", "qdrant_client.models"):
        monkeypatch.delitem(sys.modules, m, raising=False)
    import src.embeddings as emb

    return emb


def test_busca_bm25_e_fusao_reais(mods):
    docs = [
        {"texto": "clienteCodigo é o código do cliente", "secao": "4.2", "fonte": "m", "pagina": 8},
        {"texto": "texto genérico sobre coisas", "secao": "1.1", "fonte": "m", "pagina": 4},
    ]
    lex = mods.busca_bm25("o que é clienteCodigo?", docs, top_k=2)
    assert lex[0]["texto"].startswith("clienteCodigo")
    assert "bm25" in lex[0]
    assert mods.busca_bm25("x", [], top_k=2) == []


def test_tok_e_fusao(mods):
    assert mods._tok("Autenticação!") in (["autenticaca"], ["autenticacao"])
    a = {"texto": "a", "secao": "", "pagina": None, "fonte": ""}
    b = {"texto": "b", "secao": "", "pagina": None, "fonte": ""}
    out = mods.fusao_rrf([a, b], [dict(b)])
    assert out[0]["texto"] == "b"  # presente nos 2 sinais vence o só-denso


def test_upsert_payload_e_buscar_pool(monkeypatch, mods, tmp_path):
    import src.embeddings as emb

    monkeypatch.setattr(emb, "embed", lambda ts: [[0.1, 0.2] for _ in ts])
    monkeypatch.setattr(emb, "embed_query", lambda q: [0.1, 0.2])
    gravados, pontos = [], []

    class P:
        def __init__(self, payload, score):
            self.payload = payload
            self.score = score

    pontos.append(P({"texto": "t1", "fonte": "m", "pagina": 2, "secao": "S"}, 0.9))
    qc, models, Client = _qdrant_stub(gravados, pontos)
    monkeypatch.setitem(sys.modules, "qdrant_client", qc)
    monkeypatch.setitem(sys.modules, "qdrant_client.models", models)
    for m in ("src.vector_qdrant",):
        monkeypatch.delitem(sys.modules, m, raising=False)
    import src.vector_qdrant as vq

    cli_holder = {}

    orig_client = vq.client
    cli = Client()
    cli_holder["c"] = cli
    monkeypatch.setattr(vq, "client", lambda: cli)
    assert vq.upsert([]) == 0
    n = vq.upsert([{"texto": "abc", "fonte": "m.pdf"}])
    assert n == 1
    p = gravados[0].payload
    assert p["fonte"] == "m.pdf" and p["pagina"] is None
    assert p["versao_chunk"] == "v2" and p["secao"] == ""
    vq.garantir_colecao(dim=2)  # já existe: no-op
    vq.wipe_colecao()
    assert cli.deleted == ["suporte_ti"]
    out = vq.buscar("t1", top_k=4)
    assert out and out[0]["texto"] == "t1"
    assert vq.buscar("zz", top_k=4) is not None
    assert orig_client is not None
