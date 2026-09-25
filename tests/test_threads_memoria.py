"""Fase 1+2: threads persistentes + memória conversacional (DuckDB temporário)."""
import src.duckdb_store as store
from src import config, graph


def _isolado(tmp_path, monkeypatch):
    db = str(tmp_path / "fase12.duckdb")
    monkeypatch.setattr(config, "DUCKDB_PATH", db)
    store.init_db()
    return db


def test_threads_crud(tmp_path, monkeypatch):
    _isolado(tmp_path, monkeypatch)
    t = store.ensure_thread(1, None)
    assert t["id"] and t["titulo"] == "Nova conversa"
    ts = store.list_threads(1)
    assert any(x["id"] == t["id"] for x in ts)
    assert store.rename_thread(1, t["id"], "VPN não conecta")
    assert store.get_thread(1, t["id"])["titulo"] == "VPN não conecta"
    store.log_interacao(1, t["id"], "oi", "olá", False)
    assert store.count_turnos(1, t["id"]) == 1
    store.delete_thread(1, t["id"])
    assert store.get_thread(1, t["id"]) is None


def test_threads_isoladas_por_usuario(tmp_path, monkeypatch):
    _isolado(tmp_path, monkeypatch)
    store.ensure_thread(1, "abc123")
    assert store.get_thread(2, "abc123") is None  # outro usuário não vê
    assert store.list_threads(2) == []


def test_historico_ordem_e_janela(tmp_path, monkeypatch):
    _isolado(tmp_path, monkeypatch)
    t = store.ensure_thread(1, None)
    for i in range(7):
        store.log_interacao(1, t["id"], f"p{i}", f"r{i}", False)
    hist = store.historico_mensagens(1, t["id"])  # default: últimos 5 turnos = 10 msgs
    assert len(hist) == 10
    assert hist[0] == {"role": "user", "content": "p2"}
    assert hist[-1] == {"role": "assistant", "content": "r6"}


def test_titulo_automatico_primeira_pergunta(tmp_path, monkeypatch):
    _isolado(tmp_path, monkeypatch)
    t = store.ensure_thread(1, None)
    novo = store.maybe_titular(1, t["id"], "Como configuro a VPN no Ubuntu?")
    assert novo and store.get_thread(1, t["id"])["titulo"].startswith("Como configuro")
    assert store.maybe_titular(1, t["id"], "outra") is None  # não sobrescreve


def test_rewrite_usa_historico_para_busca(monkeypatch):
    vistos = {}

    class FakeLLM:
        def invoke(self, msgs):
            vistos["n"] = len(msgs)
            m = type("M", (), {"content": "qual o passo 2 da VPN no Ubuntu?"})()
            return m

    import src.llm_client as llm

    monkeypatch.setattr(llm, "get_llm", lambda verbose=False: FakeLLM())
    out = graph.reescrever({
        "pergunta": "e o passo 2?",
        "historico": [{"role": "user", "content": "como configuro a VPN no Ubuntu?"}],
        "resumo": "",
    })
    assert out["busca"] == "qual o passo 2 da VPN no Ubuntu?"


def test_rewrite_sem_historico_nao_chama_llm(monkeypatch):
    def boom(verbose=False):
        raise AssertionError("não deveria chamar LLM sem histórico")

    import src.llm_client as llm

    monkeypatch.setattr(llm, "get_llm", boom)
    out = graph.reescrever({"pergunta": "oi", "historico": [], "resumo": ""})
    assert out["busca"] == "oi"


def test_gerar_resumo_fallback_sem_llm(monkeypatch):
    import src.llm_client as llm

    def boom(verbose=False):
        raise RuntimeError("sem chave")

    monkeypatch.setattr(llm, "get_llm", boom)
    assert graph.gerar_resumo("antigo", [{"role": "user", "content": "x"}]) == "antigo"


def test_responder_aceita_historico_e_resumo(monkeypatch):
    import sys
    import types

    stub = types.ModuleType("src.vector_qdrant")
    stub.buscar = lambda *a, **k: []
    monkeypatch.setitem(sys.modules, "src.vector_qdrant", stub)
    out = graph.responder("e ele?", historico=[{"role": "user", "content": "vpn?"}],
                          resumo="usuário usa Ubuntu")
    assert out["escalado"] is True and out["resposta"]
