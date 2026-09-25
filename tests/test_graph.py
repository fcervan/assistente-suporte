from src import graph


def test_triagem_infra():
    out = graph.triagem({"pergunta": "não consigo login na vpn"})
    assert out["categoria"] == "infra"


def test_grade_escala_sem_trechos():
    assert graph.grade({"pergunta": "x", "trechos": [], "urgente": False}) == "escalar"


def test_grade_escala_trechos_irrelevantes():
    baixo = [{"texto": "x", "dense": 0.10}]
    assert graph.grade({"pergunta": "x", "trechos": baixo, "urgente": False}) == "escalar"


def test_grade_gera_trechos_relevantes():
    alto = [{"texto": "x", "dense": 0.44}]
    assert graph.grade({"pergunta": "x", "trechos": alto, "urgente": False}) == "gerar"
    sem_score = [{"texto": "x"}]  # stubs/antigos sem "dense" seguem p/ gerar
    assert graph.grade({"pergunta": "x", "trechos": sem_score, "urgente": False}) == "gerar"


def test_escalar_mensagem():
    out = graph.escalar({"pergunta": "x"})
    assert out["escalado"] is True and "humano" in out["resposta"].lower()


def test_responder_sem_qdrant_nao_quebra(monkeypatch):
    import sys
    import types

    stub = types.ModuleType("src.vector_qdrant")
    stub.buscar = lambda *a, **k: []
    monkeypatch.setitem(sys.modules, "src.vector_qdrant", stub)
    out = graph.responder("reset de senha?")
    assert out["escalado"] is True
    assert out["resposta"]
