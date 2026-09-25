"""Cobre graph nos caminhos com LLM (FakeLLM) + reescrever/gerar/resumo."""

import sys
import types

import src.llm_client as llm
from src import graph


def _stub_src(monkeypatch, name, mod):
    """Stub que vale p/ `from . import x` (sys.modules + atributo do pacote)."""
    import src as _pkg

    monkeypatch.setitem(sys.modules, f"src.{name}", mod)
    monkeypatch.setattr(_pkg, name, mod, raising=False)


class FakeLLM:
    def __init__(self, texto="TEXTO_FAKE"):
        self.texto = texto
        self.vistos = []

    def invoke(self, msgs):
        self.vistos.append(msgs)
        return types.SimpleNamespace(content=self.texto)


def _fake_llm(monkeypatch, texto="TEXTO_FAKE"):
    fake = FakeLLM(texto)
    monkeypatch.setattr(llm, "get_llm", lambda verbose=False: fake)
    return fake


def test_reescrever_com_hist_e_resumo(monkeypatch):
    fake = _fake_llm(monkeypatch, "busca condensada")
    out = graph.reescrever(
        {
            "pergunta": "e ele?",
            "historico": [
                {"role": "user", "content": "fale da VPN"},
                {"role": "assistant", "content": "vpn ok"},
            ],
            "resumo": "usuário usa Ubuntu",
        }
    )
    assert out["busca"] == "busca condensada"
    prompt = "\n".join(str(m.content) for m in fake.vistos[0])
    assert "Ubuntu" in prompt and "VPN" in prompt


def test_gerar_com_llm_e_historico(monkeypatch):
    fake = _fake_llm(monkeypatch, "Resposta final")
    out = graph.gerar(
        {
            "pergunta": "e o passo 2?",
            "trechos": [{"fonte": "m.pdf", "texto": "passo 2: clique em X", "pagina": 7}],
            "historico": [
                {"role": "user", "content": "passo 1?"},
                {"role": "assistant", "content": "faça Y"},
            ],
            "resumo": "contexto ABC",
        }
    )
    assert out["resposta"] == "Resposta final"
    assert out["provedor"] == "llm" and out["escalado"] is False
    prompt = "\n".join(str(m.content) for m in fake.vistos[0])
    assert "ABC" in prompt and "passo 2: clique em X" in prompt


def test_gerar_extrativo_sem_chave(monkeypatch):
    monkeypatch.setattr(
        llm, "get_llm", lambda verbose=False: (_ for _ in ()).throw(RuntimeError("sem chave"))
    )
    out = graph.gerar(
        {
            "pergunta": "x",
            "trechos": [{"fonte": "m.pdf", "texto": "conteúdo base", "pagina": 3}],
        }
    )
    assert out["provedor"] == "extrativo" and "conteúdo base" in out["resposta"]


def test_gerar_resumo_ok(monkeypatch):
    _fake_llm(monkeypatch, "Resumo novo")
    novo = graph.gerar_resumo("antigo", [{"role": "user", "content": "oi"}])
    assert novo == "Resumo novo"
    assert graph.gerar_resumo("antigo", []) == "antigo"


def test_responder_caminho_gerar(monkeypatch):
    stub = types.ModuleType("src.vector_qdrant")
    stub.buscar = lambda *a, **k: [{"fonte": "m.pdf", "texto": "t", "pagina": 1}]
    _stub_src(monkeypatch, "vector_qdrant", stub)
    _fake_llm(monkeypatch, "Final")
    out = graph.responder("como autentico?")
    assert out["resposta"] == "Final" and out["escalado"] is False
    assert out["fontes"] and out["busca"] == "como autentico?"


def test_formatar_historico():
    assert graph.formatar_historico(None) == ""
    txt = graph.formatar_historico(
        [{"role": "user", "content": "oi"}, {"role": "x", "content": "bot"}]
    )
    assert "Usuário: oi" in txt and "Assistente: bot" in txt


def test_system_tem_glossario_e_desambiguacao():
    assert "encomenda" in graph.SYSTEM and "pedido a pedido" in graph.SYSTEM


def test_recuperar_com_erro_nao_quebra(monkeypatch):
    class Boom:
        def buscar(self, *a, **k):
            raise ConnectionError("qdrant down")

    _stub_src(monkeypatch, "vector_qdrant", Boom())
    out = graph.recuperar({"pergunta": "x", "busca": "y"})
    assert out["trechos"] == []


def test_triagem_e_grade_ramos():
    assert graph.triagem({"pergunta": "erro na API do banco"})["categoria"] == "sistema"
    assert graph.triagem({"pergunta": "bom dia"})["categoria"] == "geral"
    assert graph.triagem({"pergunta": "tudo parado, urgente"})["urgente"] is True
    assert graph.grade({"trechos": [{"t": 1}], "urgente": True}) == "gerar"
    assert graph.grade({"trechos": [{"t": 1}], "urgente": False}) == "gerar"
