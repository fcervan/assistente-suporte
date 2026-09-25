"""chunk_docling (v2): seção/página/tabelas a partir do JSON do Docling."""

from src import chunk


def _doc():
    def T(ref, label, text, page):
        return {"self_ref": ref, "label": label, "text": text, "prov": [{"page_no": page}]}

    return {
        "texts": [
            T("#/texts/0", "page_header", "TOTAL EXPRESS", 1),
            T("#/texts/1", "section_header", "4. Método Registrar", 7),
            T(
                "#/texts/2",
                "text",
                "Cada transmissão pode conter um ou mais volumes. " "Requisição no Anexo B.",
                7,
            ),
            T("#/texts/3", "page_footer", "Página 7", 7),
            T("#/texts/4", "section_header", "4.1 Exceções", 7),
            T("#/texts/5", "code", "curl -X POST https://api/exemplo", 8),
        ],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "prov": [{"page_no": 7}],
                "data": {
                    "table_cells": [
                        {"text": "Campo", "start_row_offset_idx": 0, "start_col_offset_idx": 0},
                        {"text": "Tipo", "start_row_offset_idx": 0, "start_col_offset_idx": 1},
                        {
                            "text": "clienteCodigo",
                            "start_row_offset_idx": 1,
                            "start_col_offset_idx": 0,
                        },
                        {"text": "string", "start_row_offset_idx": 1, "start_col_offset_idx": 1},
                    ]
                },
            }
        ],
        "body": {
            "children": [
                {"$ref": "#/texts/0"},
                {"$ref": "#/texts/1"},
                {"$ref": "#/texts/2"},
                {"$ref": "#/tables/0"},
                {"$ref": "#/texts/3"},
                {"$ref": "#/texts/4"},
                {"$ref": "#/texts/5"},
            ]
        },
    }


def test_agrupa_por_secao_e_descarta_header_footer():
    chunks = chunk.chunk_docling(_doc(), fonte="m.pdf", doc_id="abc")
    textos = "\n".join(c["texto"] for c in chunks)
    assert "TOTAL EXPRESS" not in textos and "Página 7" not in textos
    assert any(c["secao"] == "4. Método Registrar" for c in chunks)
    assert any(c["secao"] == "4.1 Exceções" for c in chunks)
    assert all(c["doc_id"] == "abc" and c["fonte"] == "m.pdf" for c in chunks)
    assert all(isinstance(c["pagina"], int) for c in chunks)


def test_tabela_vira_chunk_proprio_inteiro():
    chunks = chunk.chunk_docling(_doc(), fonte="m.pdf", doc_id="abc")
    tabs = [c for c in chunks if "Tabela" in c["texto"]]
    assert len(tabs) == 1
    assert "clienteCodigo" in tabs[0]["texto"] and "string" in tabs[0]["texto"]
    assert tabs[0]["pagina"] == 7


def test_code_preservado_e_com_secao():
    chunks = chunk.chunk_docling(_doc(), fonte="m.pdf", doc_id="abc")
    codes = [c for c in chunks if "curl -X POST" in c["texto"]]
    assert len(codes) == 1 and codes[0]["secao"] == "4.1 Exceções"


def test_chunk_index_sequencial():
    chunks = chunk.chunk_docling(_doc(), fonte="m.pdf", doc_id="abc")
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_doc_vazio():
    assert chunk.chunk_docling({}, fonte="x", doc_id="y") == []
    assert chunk.chunk_docling({"texts": [], "tables": [], "body": {"children": []}}) == []


def test_sentenca_gigante_e_partida():
    longa = "palavra " * 400  # ~400 tokens, sem ponto final
    sents = chunk._sentencas(longa)
    assert len(sents) > 1
    assert "".join(sents).replace(" ", "") == longa.replace(" ", "")
    assert chunk._sentencas("") == [] and chunk._sentencas("  ") == []
    assert chunk._pagina_de({}) is None
    assert chunk._pagina_de({"prov": [{"page_no": 5}]}) == 5
    assert chunk._pagina_de({"prov": ["x"]}) is None


def test_tabela_grande_vira_blocos_com_header():
    cells = [
        {"text": "Campo", "start_row_offset_idx": 0, "start_col_offset_idx": 0},
        {"text": "Tipo", "start_row_offset_idx": 0, "start_col_offset_idx": 1},
    ]
    for i in range(1, 60):
        cells.append(
            {
                "text": f"campo{i} com descricao longa " * 4,
                "start_row_offset_idx": i,
                "start_col_offset_idx": 0,
            }
        )
        cells.append({"text": "string", "start_row_offset_idx": i, "start_col_offset_idx": 1})
    cells.append({"text": "x", "start_row_offset_idx": "ruim", "start_col_offset_idx": 0})
    blocos = chunk._tabela_blocos({"data": {"table_cells": cells}})
    assert len(blocos) > 1
    assert all(b.splitlines()[0].startswith("| Campo") for b in blocos)
    assert chunk._tabela_blocos({}) == []
    assert chunk._tabela_blocos({"data": {"table_cells": []}}) == []


def test_tabela_antes_do_cabecalho_herda_secao_seguinte():
    def T(ref, label, text, page):
        return {"self_ref": ref, "label": label, "text": text, "prov": [{"page_no": page}]}

    doc = {
        "texts": [T("#/texts/0", "section_header", "S1", 1), T("#/texts/1", "text", "corpo", 1)],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "prov": [{"page_no": 1}],
                "data": {
                    "table_cells": [
                        {"text": "A", "start_row_offset_idx": 0, "start_col_offset_idx": 0}
                    ]
                },
            }
        ],
        "body": {
            "children": [{"$ref": "#/tables/0"}, {"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}]
        },
    }
    chunks = chunk.chunk_docling(doc, fonte="m", doc_id="d")
    tabs = [c for c in chunks if "Tabela" in c["texto"]]
    assert len(tabs) == 1 and tabs[0]["secao"] == "S1"
    assert all(c["chunk_index"] == i for i, c in enumerate(chunks))


def test_tabela_pagina_anterior_herda_no_pos_passe():
    # Tabela p.1 sem âncora no body + 1º cabeçalho só na p.2: emite com
    # seção vazia e o pós-passe preenche com a seção seguinte.
    def T(ref, label, text, page):
        return {"self_ref": ref, "label": label, "text": text, "prov": [{"page_no": page}]}

    doc = {
        "texts": [
            T("#/texts/0", "text", "prefácio curto aqui", 1),
            T("#/texts/1", "section_header", "Capítulo", 2),
            T("#/texts/2", "text", "conteudo longo suficiente para passar no filtro", 2),
        ],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "prov": [{"page_no": 1}],
                "data": {
                    "table_cells": [
                        {"text": "A", "start_row_offset_idx": 0, "start_col_offset_idx": 0}
                    ]
                },
            }
        ],
        "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}, {"$ref": "#/texts/2"}]},
    }
    chunks = chunk.chunk_docling(doc, fonte="m", doc_id="d")
    tabs = [c for c in chunks if "Tabela" in c["texto"]]
    assert len(tabs) == 1 and tabs[0]["secao"] == "Capítulo"


def test_csv_linhas_vazio():
    assert chunk.chunk_csv_linhas("") == []
    assert chunk.chunk_csv_linhas("   \n  ") == []
