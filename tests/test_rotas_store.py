"""Cobre auth/main/duckdb_store/llm_client/reingest/eval sem deps pesadas."""

import sys
import types

import pytest
from fastapi import HTTPException
from src import auth, config, llm_client, main, schemas
from src import duckdb_store as store


def _stub_src(monkeypatch, name, mod):
    """Stub que vale p/ `from . import x` (sys.modules + atributo do pacote)."""
    import src as _pkg

    monkeypatch.setitem(sys.modules, f"src.{name}", mod)
    monkeypatch.setattr(_pkg, name, mod, raising=False)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DUCKDB_PATH", str(tmp_path / "c.duckdb"))
    store.init_db()
    return store


@pytest.fixture()
def user(db, tmp_path, monkeypatch):
    _stub_src(monkeypatch, "vector_qdrant", types.SimpleNamespace(buscar=lambda *a, **k: []))
    return store.create_user("T", "t@t.t", auth.hash_senha("123456"), "user")


def test_auth_atual_e_admin(db):
    u = store.create_user("A", "a@a", auth.hash_senha("123456"), "admin")
    creds = types.SimpleNamespace(credentials=auth.token(u))
    assert auth.atual(creds)["email"] == "a@a"
    assert auth.admin(u)["role"] == "admin"
    with pytest.raises(HTTPException):
        auth.atual(types.SimpleNamespace(credentials="invalido"))
    with pytest.raises(HTTPException):
        auth.admin({"role": "user"})
    assert auth.check_senha("123456", auth.hash_senha("123456")) is True


def test_main_auth_tickets(db):
    with pytest.raises(HTTPException):
        main.register(schemas.RegisterIn(nome="A", email="a@a", senha="123456"))
        main.register(schemas.RegisterIn(nome="A", email="a@a", senha="123456"))
    u = store.get_user_by_email("a@a")
    assert main.me(u)["email"] == "a@a"
    with pytest.raises(HTTPException):
        main.login(schemas.LoginIn(email="a@a", senha="errada"))
    tok = main.login(schemas.LoginIn(email="a@a", senha="123456"))
    assert tok["access_token"]
    assert main.tickets(u) == []
    assert main.health() == {"ok": True}


def test_main_threads_404(db):
    u = store.create_user("B", "b@b", auth.hash_senha("123456"), "user")
    with pytest.raises(HTTPException):
        main.thread_msgs("nope", u)
    with pytest.raises(HTTPException):
        main.renomear_thread("nope", schemas.ThreadRenameIn(titulo="x"), u)
    with pytest.raises(HTTPException):
        main.apagar_thread("nope", u)
    t = main.criar_thread(schemas.ThreadCreateIn(titulo="Título X"), u)
    assert t.titulo == "Título X"


def test_store_leituras(db):
    u = store.create_user("C", "c@c", auth.hash_senha("123456"), "user")
    assert store.get_user_by_email("n@o") is None
    store.ensure_thread(u["id"], "t1")
    store.log_interacao(u["id"], "t1", "p?", "r!", True)
    assert store.count_turnos(u["id"], "t1") == 1
    assert store.get_resumo(u["id"], "t1") == ""
    store.update_resumo(u["id"], "t1", "res")
    assert store.get_resumo(u["id"], "t1") == "res"
    msgs = store.mensagens_thread(u["id"], "t1")
    assert msgs[0]["pergunta"] == "p?" and msgs[0]["escalado"] is True
    ult = store.ultimas_interacoes(u["id"])
    assert ult and ult[0]["thread"] == "t1"
    assert store.titulo_de("  oi  ") == "oi"
    assert store.titulo_de("") == store.TITULO_PADRAO
    assert store.rename_thread(u["id"], "t1", "  Novo  ") is True
    assert store.get_thread(u["id"], "t1")["titulo"] == "Novo"
    assert store.get_thread(999, "t1") is None
    lst = store.list_threads(u["id"])
    assert lst[0]["tem_resumo"] is True and lst[0]["mensagens"] == 2


def test_store_observabilidade_rag(db):
    """Post-mortem RAG: busca/trechos/provedor persistidos por interação."""
    u = store.create_user("E", "e@e", auth.hash_senha("123456"), "user")
    store.ensure_thread(u["id"], "t9")
    trechos = [
        {
            "fonte": "m.pdf",
            "pagina": 7,
            "secao": "4. Método Registrar",
            "texto": "x" * 5000,  # texto integral NÃO é persistido
            "score": 0.016,
            "dense": 0.44,
        }
    ]
    store.log_interacao(
        u["id"], "t9", "p?", "r!", False, busca="busca x", trechos=trechos, provedor="llm"
    )
    ult = store.ultimas_interacoes(u["id"])
    assert ult[0]["busca"] == "busca x" and ult[0]["provedor"] == "llm"
    assert ult[0]["trechos"][0]["fonte"] == "m.pdf"
    assert "texto" not in ult[0]["trechos"][0]


def test_migracao_db_legado_sem_colunas(tmp_path, monkeypatch):
    """DBs criados antes da observabilidade ganham busca/trechos/provedor via ALTER."""
    monkeypatch.setattr(config, "DUCKDB_PATH", str(tmp_path / "legado.duckdb"))
    with store.connect() as con:
        con.execute(
            "CREATE TABLE interacoes(id INTEGER PRIMARY KEY, ticket_id INTEGER,"
            " user_id INTEGER, thread_id VARCHAR, pergunta VARCHAR, resposta VARCHAR,"
            " escalado BOOLEAN DEFAULT FALSE,"
            " criado_em TIMESTAMP DEFAULT current_timestamp)"
        )
        con.execute("CREATE SEQUENCE IF NOT EXISTS seq_interacoes START 1")
    store.init_db()  # migra sem perder nada
    store.log_interacao(1, "t", "p", "r", False, busca="b", trechos=[], provedor="regra")
    ult = store.ultimas_interacoes(1)
    assert ult[0]["busca"] == "b" and ult[0]["trechos"] == [] and ult[0]["provedor"] == "regra"


def test_backfill_threads_antigas(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DUCKDB_PATH", str(tmp_path / "b.duckdb"))
    store.init_db()
    u = store.create_user("D", "d@d", auth.hash_senha("123456"), "user")
    store.log_interacao(u["id"], "legada", "pergunta antiga?", "resp", False)
    with store.connect() as con:
        con.execute("DROP TABLE threads")
    store.init_db()  # recria + backfill
    t = store.get_thread(u["id"], "legada")
    assert t and t["titulo"].startswith("pergunta antiga")


def test_llm_client_sem_chaves(monkeypatch):
    for k in ("GROQ_API_KEY", "OLLAMA_CLOUD_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError):
        llm_client.get_llm(verbose=False)
    mods = llm_client.effective_models()
    assert set(mods) == {"groq", "ollama", "openrouter"}
    monkeypatch.setenv("GROQ_MODEL", "m-x")
    assert llm_client.effective_models()["groq"] == "m-x"


def test_llm_client_groq_ok(monkeypatch):
    fake_mod = types.ModuleType("langchain_groq")

    class FakeGroq:
        def __init__(self, model, api_key):
            self.model = model

    fake_mod.ChatGroq = FakeGroq
    monkeypatch.setitem(sys.modules, "langchain_groq", fake_mod)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    assert llm_client.get_llm(verbose=False).model == "openai/gpt-oss-20b"


def test_llm_client_fallthrough(monkeypatch):
    """Groq falha no import -> Ollama; Ollama falha -> OpenRouter; tudo falha -> erro."""
    for k in ("GROQ_API_KEY", "OLLAMA_CLOUD_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delitem(sys.modules, "langchain_groq", raising=False)
    quebrado = types.ModuleType("langchain_groq")  # sem ChatGroq -> ImportError
    monkeypatch.setitem(sys.modules, "langchain_groq", quebrado)
    fake_mod = types.ModuleType("langchain_openai")

    class FakeOI:
        def __init__(self, model, api_key, base_url):
            if "ollama" in base_url:
                raise ConnectionError("ollama down")
            self.base_url = base_url

    fake_mod.ChatOpenAI = FakeOI
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_mod)
    monkeypatch.setenv("GROQ_API_KEY", "k")  # import quebra -> pula p/ Ollama
    monkeypatch.setenv("OLLAMA_CLOUD_API_KEY", "k2")  # init quebra -> OpenRouter
    monkeypatch.setenv("OPENROUTER_API_KEY", "k3")
    assert llm_client.get_llm(verbose=False).base_url == "https://openrouter.ai/api/v1"
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(RuntimeError):
        llm_client.get_llm(verbose=False)


def test_chat_stream(user):
    import asyncio

    resp = main.chat_stream(schemas.ChatIn(mensagem="oi", thread_id=""), user)
    assert resp.status_code == 200

    async def coletar():
        return [c async for c in resp.body_iterator]

    partes = asyncio.run(coletar())
    texto = "".join(c.decode() if isinstance(c, bytes) else c for c in partes)
    assert "[DONE]" in texto


def test_ingest_csv_e_md(tmp_path, monkeypatch, user):
    import io
    from pathlib import Path

    from fastapi import UploadFile

    monkeypatch.chdir(tmp_path)
    admin = {**user, "role": "admin"}

    def fake_converter(origem: Path, destino_dir: Path) -> dict:
        destino_dir.mkdir(parents=True, exist_ok=True)
        base = origem.stem
        md = destino_dir / f"{base}.md"
        js = destino_dir / f"{base}.json"
        if origem.suffix == ".csv":
            md.write_text("a;b\n1;2", encoding="utf-8")
            js.write_text("{}", encoding="utf-8")
        elif base == "comjson":
            md.write_text("oi", encoding="utf-8")
            js.write_text(
                '{"texts": [{"self_ref": "#/texts/0", "label": "text",'
                ' "text": "conteudo util aqui para teste de ingestao com varias'
                ' palavras extras suficientes", "prov": [{"page_no": 3}]}],'
                ' "tables": [], "body": {"children": [{"$ref": "#/texts/0"}]},'
                ' "origin": {"filename": "comjson.md", "binary_hash": 7}}',
                encoding="utf-8",
            )
        else:
            md.write_text("texto simples de fallback", encoding="utf-8")
            js.write_text("{}", encoding="utf-8")
        return {"md_path": str(md), "json_path": str(js), "tabelas": 0}

    ing_mod = types.ModuleType("src.ingest_docling")
    ing_mod.converter_arquivo = fake_converter
    _stub_src(monkeypatch, "ingest_docling", ing_mod)
    gravados = []
    vq_mod = types.ModuleType("src.vector_qdrant")
    vq_mod.upsert = lambda chunks: gravados.extend(chunks) or len(chunks)
    _stub_src(monkeypatch, "vector_qdrant", vq_mod)

    def up(nome, conteudo=b"x"):
        return UploadFile(filename=nome, file=io.BytesIO(conteudo))

    out = main.ingest(files=[up("a.csv"), up("comjson.md"), up("plano.md")], user=admin)
    assert out["arquivos"] == 3 and out["chunks"] == len(gravados) > 0
    assert any(g.get("secao") == "" and "conteudo util" in g["texto"] for g in gravados)


def test_llm_client_ollama_e_openrouter(monkeypatch):
    for k in ("GROQ_API_KEY", "OLLAMA_CLOUD_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    fake_mod = types.ModuleType("langchain_openai")

    class FakeOI:
        def __init__(self, model, api_key, base_url):
            self.model = model
            self.base_url = base_url

    fake_mod.ChatOpenAI = FakeOI
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_mod)
    monkeypatch.setenv("OLLAMA_CLOUD_API_KEY", "k2")
    cli = llm_client.get_llm(verbose=False)
    assert cli.base_url == "https://ollama.com/v1"
    monkeypatch.delenv("OLLAMA_CLOUD_API_KEY")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k3")
    cli = llm_client.get_llm(verbose=False)
    assert cli.base_url == "https://openrouter.ai/api/v1"


def test_reingest_doc_meta(tmp_path):
    from src.reingest_v2 import doc_meta

    assert doc_meta(tmp_path / "inexistente.json")[0] == "inexistente"
    jp = tmp_path / "d.json"
    jp.write_text('{"origin": {"filename": "a.pdf", "binary_hash": 42}}', encoding="utf-8")
    fonte, doc_id, doc = doc_meta(jp)
    assert (fonte, doc_id) == ("a.pdf", "42") and doc["origin"]["filename"] == "a.pdf"


def test_eval_carregar_e_norm():
    from src.eval_douradas import carregar, norm

    casos = carregar("tests/douradas.csv")
    assert len(casos) == 16 and all(kws for _, kws in casos)
    assert norm("Autenticação 200!") == "autenticacao 200!"
