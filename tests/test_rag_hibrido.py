"""RRF com pesos iguais: literal exato (BM25) pode vencer o denso."""
import pytest

embeddings = pytest.importorskip("src.embeddings",
                                 reason="sem deps vetoriais locais")


def test_bm25_primeiro_vence_denso_primeiro():
    a = {"texto": "a"}  # denso #1, sem o termo
    b = {"texto": "b clienteCodigo"}  # BM25 #1
    out = embeddings.fusao_rrf([a, b], [b, a])
    assert out[0]["texto"] == "b clienteCodigo"


def test_fusao_soma_sinais_de_copias():
    # busca_bm25 devolve CÓPIAS dos dicts: mesmo conteúdo, outro id().
    # A fusão precisa somar os dois sinais no mesmo documento.
    orig = {"texto": "x", "secao": "s", "pagina": 1, "fonte": "f"}
    copia = dict(orig)
    assert id(orig) != id(copia)
    out = embeddings.fusao_rrf([orig], [copia])
    assert len(out) == 1  # sem duplicar
    assert out[0]["score"] == round(0.5 / 61 + 0.5 / 61, 6)  # somou


def test_tok_normaliza():
    assert embeddings._tok("Autenticação? Response 200!") == ["autenticacao", "response", "200"]
    assert embeddings._tok("") == []
