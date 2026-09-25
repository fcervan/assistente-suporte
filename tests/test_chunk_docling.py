"""chunk_docling (v2): seção/página/tabelas a partir do JSON do Docling."""
from src import chunk


def _doc():
    def T(ref, label, text, page):
        return {"self_ref": ref, "label": label, "text": text,
                "prov": [{"page_no": page}]}
    return {
        "texts": [
            T("#/texts/0", "page_header", "TOTAL EXPRESS", 1),
            T("#/texts/1", "section_header", "4. Método Registrar", 7),
            T("#/texts/2", "text", "Cada transmissão pode conter um ou mais volumes. "
                                   "Requisição no Anexo B.", 7),
            T("#/texts/3", "page_footer", "Página 7", 7),
            T("#/texts/4", "section_header", "4.1 Exceções", 7),
            T("#/texts/5", "code", "curl -X POST https://api/exemplo", 8),
        ],
        "tables": [{
            "self_ref": "#/tables/0",
            "prov": [{"page_no": 7}],
            "data": {"table_cells": [
                {"text": "Campo", "start_row_offset_idx": 0, "start_col_offset_idx": 0},
                {"text": "Tipo", "start_row_offset_idx": 0, "start_col_offset_idx": 1},
                {"text": "clienteCodigo", "start_row_offset_idx": 1,
                 "start_col_offset_idx": 0},
                {"text": "string", "start_row_offset_idx": 1, "start_col_offset_idx": 1},
            ]},
        }],
        "body": {"children": [
            {"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}, {"$ref": "#/texts/2"},
            {"$ref": "#/tables/0"}, {"$ref": "#/texts/3"}, {"$ref": "#/texts/4"},
            {"$ref": "#/texts/5"},
        ]},
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
    assert chunk.chunk_docling({"texts": [], "tables": [],
                                "body": {"children": []}}) == []
