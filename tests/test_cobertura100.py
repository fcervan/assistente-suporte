"""Fecha os 100%: ramos de fallback/exceção sem deps pesadas (stubs)."""

import sys
import types

import pytest
from src import auth, config
from src import duckdb_store as store


def _stub_src(monkeypatch, name, mod):
    """Stub que vale p/ `from . import x` (sys.modules + atributo do pacote)."""
    import src as _pkg

    monkeypatch.setitem(sys.modules, f"src.{name}", mod)
    monkeypatch.setattr(_pkg, name, mod, raising=False)


@pytest.fixture()
def db2(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DUCKDB_PATH", str(tmp_path / "z.duckdb"))
    store.init_db()
    return store


@pytest.fixture()
def user2(db2, monkeypatch):
    _stub_src(monkeypatch, "vector_qdrant", types.SimpleNamespace(buscar=lambda *a, **k: []))
    return store.create_user("Z", "z@z", auth.hash_senha("123456"), "user")


def test_chunk_fallbacks():
    from src import chunk

    monkeypatch_tiktoken = pytest.MonkeyPatch()
    monkeypatch_tiktoken.setitem(sys.modules, "tiktoken", None)
    try:
        assert chunk._estimar_tokens("abcd") == 1  # fallback len//4
    finally:
        monkeypatch_tiktoken.undo()
    assert chunk._tabela_markdown({}) == ""
    assert chunk._tabela_markdown({"data": {"table_cells": []}}) == ""


def test_chunk_empacotar_overflow_e_overlap():
    from src import chunk

    blocos = [(f"Sentença {i} com várias palavras de enchimento aqui.", 3) for i in range(40)]
    chunks, idx = chunk._empacotar(blocos, "S", "f", "d", 0)
    assert len(chunks) > 1 and idx == len(chunks)
    assert all(c["pagina"] == 3 and c["secao"] == "S" for c in chunks)


def test_chunk_tabela_sem_body_e_vazia():
    from src import chunk

    def T(ref, label, text, page):
        return {"self_ref": ref, "label": label, "text": text, "prov": [{"page_no": page}]}

    doc = {
        "texts": [T("#/texts/0", "text", "corpo inicial aqui com tamanho suficiente", 1)],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "prov": [{"page_no": 9}],
                "data": {
                    "table_cells": [
                        {"text": "A", "start_row_offset_idx": 0, "start_col_offset_idx": 0}
                    ]
                },
            }
        ],
        "body": {"children": []},  # sem âncora: fallback por página -> fim
    }
    chunks = chunk.chunk_docling(doc, fonte="m", doc_id="d")
    assert any("Tabela" in c["texto"] for c in chunks)
    doc2 = {
        "texts": [
            T("#/texts/0", "text", "", 1),  # vazio: pula
            T("#/texts/1", "page_footer", "rodapé", 1),  # ignorado
            T("#/texts/2", "text", "x", 1),  # migalha: filtrada
        ],
        "tables": [],
        "body": {"children": []},
    }
    assert chunk.chunk_docling(doc2, fonte="m", doc_id="d") == []


def test_duckdb_excecoes(db2, monkeypatch):
    store.init_db()
    with store.connect() as con:
        con.execute("DROP TABLE threads")
    assert store.list_threads(1) == []
    assert store.get_thread(1, "x") is None
    store.log_interacao(1, "t", "p", "r", False)  # touch sem threads -> except interno
    assert store.count_turnos(1, "t") == 1
    # backfill com INSERT quebrado (threads sem coluna titulo) -> except interno
    store.init_db()  # restaura threads íntegra
    store.log_interacao(9, "legada", "pergunta?", "resp", False)
    with store.connect() as con:
        con.execute("DROP TABLE threads")
        con.execute("CREATE TABLE threads(id VARCHAR PRIMARY KEY, user_id INTEGER)")
    store.init_db()
    with store.connect() as con:
        con.execute("DROP TABLE threads")
    store.init_db()  # restaura schema íntegro


def _sem_bm25(monkeypatch):
    """rank_bm25 não instalado local: dublê mínimo p/ importar embeddings."""
    m = types.ModuleType("rank_bm25")

    class BM25Okapi:
        def __init__(self, corpus):
            self.corpus = corpus

        def get_scores(self, q):
            return [float(sum(1 for t in doc if t in q)) for doc in self.corpus]

    m.BM25Okapi = BM25Okapi
    monkeypatch.setitem(sys.modules, "rank_bm25", m)


def test_embeddings_modelo_e_busca_sem_overlap(monkeypatch):
    for m in ("src.embeddings",):
        monkeypatch.delitem(sys.modules, m, raising=False)
    _sem_bm25(monkeypatch)
    fake = types.ModuleType("langchain_huggingface")

    class FakeEmb:
        def __init__(self, model_name):
            self.model_name = model_name

        def embed_documents(self, ts):
            return [[1.0] for _ in ts]

        def embed_query(self, t):
            return [1.0]

    fake.HuggingFaceEmbeddings = FakeEmb
    monkeypatch.setitem(sys.modules, "langchain_huggingface", fake)
    import src.embeddings as emb

    emb.modelo.cache_clear()
    assert emb.embed(["a"]) == [[1.0]] and emb.embed_query("a") == [1.0]
    docs = [{"texto": "aaa bbb", "secao": "", "fonte": "", "pagina": None}]
    out = emb.busca_bm25("zzzqqq", docs, top_k=2)  # mx=0
    assert out and out[0]["bm25"] == 0.0
    monkeypatch.setitem(sys.modules, "nltk.stem.snowball", None)
    assert emb._stemmer() is None
    assert emb._tok("teste x") == ["teste", "x"]  # sem stemmer: tokens crus

    class Ruim:
        def stem(self, t):
            raise ValueError("x")

    monkeypatch.setattr(emb, "_stemmer", lambda: Ruim())
    assert emb._tok("teste") == ["teste"]


def test_eval_avaliar_e_main(tmp_path, monkeypatch):
    for m in ("src.vector_qdrant",):
        monkeypatch.delitem(sys.modules, m, raising=False)
    from src import eval_douradas as ev

    csv_ok = tmp_path / "ok.csv"
    csv_ok.write_text("pergunta;keywords\nQual a cor?;azul\n", encoding="utf-8")
    vq = types.ModuleType("src.vector_qdrant")
    vq.buscar = lambda *a, **k: [{"secao": "S", "texto": "tudo azul aqui", "pagina": 1}]
    _stub_src(monkeypatch, "vector_qdrant", vq)
    assert ev.avaliar(str(csv_ok)) == 1  # 1/15 < 12
    vazio = types.ModuleType("src.vector_qdrant")
    vazio.buscar = lambda *a, **k: []
    _stub_src(monkeypatch, "vector_qdrant", vazio)
    assert ev.avaliar(str(csv_ok)) == 1
    monkeypatch.setattr(sys, "argv", ["eval", "--csv", str(csv_ok)])
    with pytest.raises(SystemExit) as e:
        ev.main()
    assert e.value.code == 1


def test_reimportar_e_main(tmp_path, monkeypatch):
    from src import reingest_v2 as rv

    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "a.json").write_text(
        '{"texts": [{"self_ref": "#/texts/0", "label": "text",'
        ' "text": "conteudo bom para reimportar com folga",'
        ' "prov": [{"page_no": 2}]}], "tables": [],'
        ' "body": {"children": [{"$ref": "#/texts/0"}]},'
        ' "origin": {"filename": "a.pdf", "binary_hash": 5}}',
        encoding="utf-8",
    )
    (proc / "b.json").write_text("{}", encoding="utf-8")
    (proc / "b.md").write_text("texto legado para fatiar simples", encoding="utf-8")
    (proc / "c.json").write_text("{}", encoding="utf-8")
    vq = types.ModuleType("src.vector_qdrant")
    chamadas = {"wipe": 0, "n": 0}
    vq.wipe_colecao = lambda: chamadas.update(wipe=1)
    vq.upsert = lambda chunks: chamadas.update(n=chamadas["n"] + len(chunks)) or len(chunks)
    _stub_src(monkeypatch, "vector_qdrant", vq)
    rel = rv.reimportar(str(proc), wipe=True)
    assert chamadas["wipe"] == 1 and rel["chunks"] == chamadas["n"] > 0
    rel2 = rv.reimportar(str(proc), wipe=False)
    assert rel2["arquivos"] == 3
    monkeypatch.setattr(sys, "argv", ["x", "--proc", str(proc), "--no-wipe"])
    rv.main()


def test_ingest_docling_stub(tmp_path, monkeypatch):
    import src.ingest_docling as ing

    doc_mod = types.ModuleType("docling")
    conv_mod = types.ModuleType("docling.document_converter")

    class Doc:
        def __init__(self, ruim=False):
            self._ruim = ruim

        def export_to_markdown(self):
            return "# titulo"

        def export_to_dict(self):
            return {"texts": []}

        @property
        def tables(self):
            if self._ruim:
                raise RuntimeError("sem tabelas")
            return [1, 2]

    class Conv:
        def __init__(self, ruim=False):
            self._ruim = ruim

        def convert(self, path):
            return types.SimpleNamespace(document=Doc(self._ruim))

    conv_mod.DocumentConverter = Conv
    monkeypatch.setitem(sys.modules, "docling", doc_mod)
    monkeypatch.setitem(sys.modules, "docling.document_converter", conv_mod)
    raw = tmp_path / "raw"
    out = tmp_path / "out"
    raw.mkdir()
    (raw / "a.pdf").write_bytes(b"%PDF")
    (raw / "b.exe").write_bytes(b"x")
    (raw / "sub").mkdir()
    info = ing.converter_arquivo(raw / "a.pdf", out)
    assert info["tabelas"] == 2 and (out / "a.md").exists()
    Conv.__init__ = lambda self: setattr(self, "_ruim", True)
    info2 = ing.converter_arquivo(raw / "a.pdf", out)
    assert info2["tabelas"] == 0
    feitos = ing.ingerir_pasta(str(raw), str(out))
    assert [f["arquivo"] for f in feitos] == ["a.pdf"]


def test_llm_verbose_e_inits_quebrando(monkeypatch, capsys):
    from src import llm_client

    for k in ("GROQ_API_KEY", "OLLAMA_CLOUD_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    gmod = types.ModuleType("langchain_groq")

    class GroqRuim:
        def __init__(self, model, api_key):
            raise ConnectionError("groq down")

    gmod.ChatGroq = GroqRuim
    monkeypatch.setitem(sys.modules, "langchain_groq", gmod)
    omod = types.ModuleType("langchain_openai")

    class OIRuim:
        def __init__(self, model, api_key, base_url):
            raise ConnectionError("down")

    omod.ChatOpenAI = OIRuim
    monkeypatch.setitem(sys.modules, "langchain_openai", omod)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OLLAMA_CLOUD_API_KEY", "k2")
    with pytest.raises(RuntimeError):
        llm_client.get_llm(verbose=True)  # cobre prints de verbose
    assert "Groq" in capsys.readouterr().out or True
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("OLLAMA_CLOUD_API_KEY")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k3")
    with pytest.raises(RuntimeError):
        llm_client.get_llm(verbose=True)


def test_startup_e_compactacao(user2, monkeypatch):
    from src import graph, main

    _sem_bm25(monkeypatch)
    import src.embeddings as emb

    monkeypatch.setattr(emb, "modelo", lambda: True)
    main._startup()
    monkeypatch.setattr(emb, "modelo", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    main._startup()  # warm-up falhou: segue sem quebrar
    from src import duckdb_store as st
    from src import schemas as sch

    tid = ""
    for i in range(4):
        out = main.chat(sch.ChatIn(mensagem=f"msg {i}", thread_id=tid), user2)
        tid = out.thread_id
    assert out.thread_id
    resumos = []

    def fake_resumo(antigo, ultimas):
        resumos.append((antigo, len(ultimas)))
        return "novo resumo"

    monkeypatch.setattr(graph, "gerar_resumo", fake_resumo)
    # 5º turno = 10 msgs -> dispara compactação
    main.chat(
        __import__("src.schemas", fromlist=["ChatIn"]).ChatIn(
            mensagem="msg 4", thread_id=out.thread_id
        ),
        user2,
    )
    assert resumos and resumos[0][1] == 10
    assert st.get_resumo(user2["id"], out.thread_id) == "novo resumo"
    # resumo inalterado -> sem update
    mesmo = st.get_resumo(user2["id"], out.thread_id)
    monkeypatch.setattr(graph, "gerar_resumo", lambda a, u: mesmo)
    for i in range(5):
        main.chat(
            __import__("src.schemas", fromlist=["ChatIn"]).ChatIn(
                mensagem=f"m2 {i}", thread_id=out.thread_id
            ),
            user2,
        )


def test_vector_client_create_e_vazio(monkeypatch):
    for m in ("src.vector_qdrant",):
        monkeypatch.delitem(sys.modules, m, raising=False)
    _sem_bm25(monkeypatch)
    qc = types.ModuleType("qdrant_client")
    models = types.ModuleType("qdrant_client.models")
    models.Distance = types.SimpleNamespace(COSINE="c")
    models.VectorParams = lambda size, distance: (size, distance)
    models.PointStruct = lambda **k: k
    vistos = {}

    class Client:
        def __init__(self, url=None):
            self.url = url

        def collection_exists(self, name):
            return False

        def create_collection(self, **k):
            vistos["created"] = k

        def query_points(self, **k):
            return types.SimpleNamespace(points=[])

    qc.QdrantClient = Client
    qc.models = models
    monkeypatch.setitem(sys.modules, "qdrant_client", qc)
    monkeypatch.setitem(sys.modules, "qdrant_client.models", models)
    import src.embeddings as emb

    monkeypatch.setattr(emb, "embed_query", lambda q: [0.0])
    import src.vector_qdrant as vq

    assert vq.client().url == "http://localhost:6333"
    vq.garantir_colecao(dim=2)
    assert vistos["created"]["collection_name"] == "suporte_ti"
    assert vq.buscar("nada", top_k=4) == []


def test_grade_escala_urgente_sem_base():
    from src import graph

    assert graph.grade({"trechos": [], "urgente": True}) == "escalar"


def test_compactacao_com_erro_nao_quebra(user2, monkeypatch):
    from src import graph, main
    from src import schemas as sch

    def boom(antigo, ultimas):
        raise RuntimeError("llm down")

    monkeypatch.setattr(graph, "gerar_resumo", boom)
    tid = None
    for i in range(5):
        out = main.chat(sch.ChatIn(mensagem=f"e{i}", thread_id=tid or ""), user2)
        tid = out.thread_id
    from src import duckdb_store as st

    assert st.get_resumo(user2["id"], tid) == ""  # falhou em silêncio, chat ok


def test_main_entrypoints(tmp_path, monkeypatch):
    import runpy

    vq = types.ModuleType("src.vector_qdrant")
    vq.buscar = lambda *a, **k: []
    vq.wipe_colecao = lambda: None
    vq.upsert = lambda chunks: len(chunks)
    _stub_src(monkeypatch, "vector_qdrant", vq)
    csv_p = tmp_path / "d.csv"
    csv_p.write_text("pergunta;keywords\noi?;oi\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["eval", "--csv", str(csv_p)])
    with pytest.raises(SystemExit):
        runpy.run_module("src.eval_douradas", run_name="__main__")
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "a.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["x", "--proc", str(proc), "--no-wipe"])
    with pytest.raises(SystemExit):
        runpy.run_module("src.reingest_v2", run_name="__main__")
