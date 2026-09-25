from src import chunk


def test_chunk_texto_basico():
    partes = chunk.chunk_texto("abcdefghij", tamanho=4, overlap=1)
    assert partes and "".join(p[0] for p in partes).startswith("a")
    assert all(p.strip() for p in partes)


def test_chunk_csv_repete_cabecalho():
    partes = chunk.chunk_csv_linhas("col1;col2\na;1\nb;2")
    assert len(partes) == 2
    assert all(p.startswith("col1;col2") for p in partes)


def test_chunk_vazio():
    assert chunk.chunk_texto("") == []
