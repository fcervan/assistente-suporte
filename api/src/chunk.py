"""Chunking: markdown/texto -> lista de chunks (tamanho/overlap do config).

v2 (chunk_docling): agrupa blocos do JSON do Docling por seção, preserva
tabelas/código inteiros, descarta header/footer e anexa pagina/secao/doc_id.
"""

from __future__ import annotations

import re

IGNORAR_LABELS = {"page_header", "page_footer", "picture", "figure"}
BLOCO_LABELS = {"text", "code", "list_item", "section_header", "title"}
# Embedder MiniLM trunca em 512 tokens: chunks ficam bem abaixo disso.
MAX_TOKENS = 300
OVERLAP_TOKENS = 60
# Migalhas de capa/rodapé (ex: "Versão 2.1", "TOTA") viram ruído no índice.
MIN_TOKENS = 10
_SINAIS_CODIGO = ("{", "}", "http", "|", "curl")

_SENT_RE = re.compile(r"(?<=[.!?…:])\s+|\n{2,}")


def _estimar_tokens(s: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(s or ""))
    except Exception:
        return len(s or "") // 4


def _sentencas(bloco: str) -> list[str]:
    partes = [p.strip() for p in _SENT_RE.split(bloco or "") if p.strip()]
    out: list[str] = []
    for p in partes or ([bloco.strip()] if (bloco or "").strip() else []):
        # Sentença gigante (ex: descrição de campo) não cabe no embedder: parte.
        while _estimar_tokens(p) > MAX_TOKENS:
            corte = len(p) * MAX_TOKENS // max(1, _estimar_tokens(p))
            quebrar = p.rfind(" ", 0, corte)
            quebrar = quebrar if quebrar > corte // 2 else corte
            out.append(p[:quebrar].strip())
            p = p[quebrar:].strip()
        if p:
            out.append(p)
    return out


def _pagina_de(item: dict) -> int | None:
    prov = item.get("prov") or []
    if prov and isinstance(prov[0], dict):
        return prov[0].get("page_no")
    return None


def _tabela_markdown(table: dict) -> str:
    blocos = _tabela_blocos(table)
    return blocos[0] if blocos else ""


def _tabela_blocos(table: dict, max_tokens: int = 300) -> list[str]:
    """Tabela em markdown; tabelas gigantes viram blocos de linhas com header
    repetido (embedder trunca em 512 tokens — bloco grande perde o rabo)."""
    data = (table or {}).get("data") or {}
    cells = data.get("table_cells") or []
    linhas: dict[int, list[tuple[int, str]]] = {}
    for c in cells:
        try:
            linhas.setdefault(int(c.get("start_row_offset_idx", 0)), []).append(
                (int(c.get("start_col_offset_idx", 0)), str(c.get("text") or "").strip())
            )
        except (TypeError, ValueError):
            continue
    grid = []
    for idx in sorted(linhas):
        cols = [t for _, t in sorted(linhas[idx])]
        if any(cols):
            grid.append("| " + " | ".join(cols) + " |")
    if not grid:
        return []
    if _estimar_tokens("\n".join(grid)) <= max_tokens:
        return ["\n".join(grid)]
    head, corpo = grid[0], grid[1:]
    blocos, atual = [], [head]
    for lin in corpo:
        if _estimar_tokens("\n".join(atual + [lin])) > max_tokens:
            blocos.append("\n".join(atual))
            atual = [head, lin]
        else:
            atual.append(lin)
    blocos.append("\n".join(atual))
    return blocos


def _empacotar(
    blocos: list[tuple[str, int | None]], secao: str, fonte: str, doc_id: str, idx0: int
) -> tuple[list[dict], int]:
    """Blocos (texto, pagina) -> chunks com overlap por sentença completa."""
    sents: list[tuple[str, int | None]] = []
    for texto, pag in blocos:
        for s in _sentencas(texto):
            sents.append((s, pag))
    chunks, atual, pags, idx = [], [], [], idx0
    for s, pag in sents:
        atual.append(s)
        pags.append(pag)
        if _estimar_tokens(" ".join(atual)) >= MAX_TOKENS:
            corpo = " ".join(atual).strip()
            pagina = next((p for p in pags if p is not None), None)
            texto = f"[Seção: {secao}]\n{corpo}" if secao else corpo
            chunks.append(
                {
                    "texto": texto,
                    "fonte": fonte,
                    "pagina": pagina,
                    "secao": secao,
                    "chunk_index": idx,
                    "doc_id": doc_id,
                }
            )
            idx += 1
            # overlap: últimas sentenças completas (~OVERLAP_TOKENS)
            keep, total = [], 0
            for sv in reversed(atual):
                total += _estimar_tokens(sv)
                keep.append(sv)
                if total >= OVERLAP_TOKENS:
                    break
            kpags = pags[-len(keep) :] if keep else []
            atual, pags = list(reversed(keep)), list(kpags)
    if any(a.strip() for a in atual):
        corpo = " ".join(atual).strip()
        pagina = next((p for p in pags if p is not None), None)
        texto = f"[Seção: {secao}]\n{corpo}" if secao else corpo
        chunks.append(
            {
                "texto": texto,
                "fonte": fonte,
                "pagina": pagina,
                "secao": secao,
                "chunk_index": idx,
                "doc_id": doc_id,
            }
        )
        idx += 1
    return chunks, idx


def chunk_docling(doc: dict, fonte: str = "", doc_id: str = "") -> list[dict]:
    """JSON do Docling (export_to_dict) -> chunks v2 com seção/página.

    Percorre texts na ordem do documento (body.children pode omitir blocos,
    ex: list_items); tabelas são intercaladas por page_no. Header/footer são
    descartados; tabelas viram chunks próprios e inteiros.
    """
    doc = doc or {}
    textos = doc.get("texts") or []
    tabelas = list(doc.get("tables") or [])

    # Posição de cada tabela no fluxo de leitura: via body.children quando
    # presente (insere após o texto anterior); senão, fallback por página.
    pos_texto = {t.get("self_ref"): i for i, t in enumerate(textos) if t.get("self_ref")}
    ancoras: dict[str, int] = {}
    filhos = ((doc.get("body") or {}).get("children")) or []
    ultimo_txt = -1
    for filho in filhos:
        ref = filho.get("$ref", "")
        if ref.startswith("#/texts/") and ref in pos_texto:
            it = textos[pos_texto[ref]]
            if it.get("label") in BLOCO_LABELS and (it.get("text") or "").strip():
                ultimo_txt = pos_texto[ref]
        elif ref.startswith("#/tables/"):
            ancoras[ref] = ultimo_txt
    pag_texto = [(_pagina_de(t) or 0) for t in textos]
    for tb in tabelas:
        if tb.get("self_ref") not in ancoras:
            pg = _pagina_de(tb) or 0
            pos = max([i for i, p in enumerate(pag_texto) if p <= pg] or [len(textos)])
            ancoras[tb.get("self_ref")] = min(pos, len(textos) - 1)
    por_pos: dict[int, list[dict]] = {}
    for tb in tabelas:
        por_pos.setdefault(ancoras.get(tb.get("self_ref"), len(textos)), []).append(tb)

    chunks: list[dict] = []
    buf: list[tuple[str, int | None]] = []
    secao, idx = "", 0

    def descarregar():
        nonlocal buf, idx
        if buf:
            novos, idx = _empacotar(buf, secao, fonte, doc_id, idx)
            chunks.extend(novos)
            buf = []

    def emitir_tabela(table: dict):
        nonlocal idx
        blocos = _tabela_blocos(table)
        for b, md in enumerate(blocos):
            pag = _pagina_de(table)
            suf = f" (parte {b + 1}/{len(blocos)})" if len(blocos) > 1 else ""
            if secao:
                texto = f"[Seção: {secao} | Tabela{suf}]\n{md}"
            else:  # tabela antes do 1º cabeçalho: seção preenchida no pós-passe
                texto = f"[Tabela{suf}]\n{md}"
            chunks.append(
                {
                    "texto": texto,
                    "fonte": fonte,
                    "pagina": pag,
                    "secao": secao,
                    "chunk_index": idx,
                    "doc_id": doc_id,
                }
            )
            idx += 1

    def descarregar_tabelas(pos: int):
        for tb in por_pos.pop(pos, []):
            descarregar()
            emitir_tabela(tb)

    for i, item in enumerate(textos):
        label = item.get("label", "")
        if label in IGNORAR_LABELS or label not in BLOCO_LABELS:
            descarregar_tabelas(i)  # âncora pode apontar p/ bloco ignorado
            continue
        txt = (item.get("text") or "").strip()
        if not txt:
            descarregar_tabelas(i)
            continue
        if label == "section_header":
            descarregar()
            secao = txt
            descarregar_tabelas(i)
            continue
        buf.append((txt, _pagina_de(item)))
        descarregar_tabelas(i)
    descarregar()
    # tabelas sem âncora válida (ex: doc sem body): vão para o fim, com contexto
    for pos in sorted(por_pos):
        for tb in por_pos[pos]:
            descarregar()
            emitir_tabela(tb)
    bons = []
    for c in chunks:
        corpo = re.sub(r"^\[Seção:[^\]]*\]\s*", "", c["texto"]).strip()
        if (
            _estimar_tokens(corpo) >= MIN_TOKENS
            or "[Tabela]" in c["texto"]
            or any(s in corpo for s in _SINAIS_CODIGO)
        ):
            bons.append(c)
    for i, c in enumerate(bons):
        c["chunk_index"] = i
    # tabelas/blocos anteriores ao 1º cabeçalho herdam a seção seguinte
    prox = ""
    for c in reversed(bons):
        if c["secao"]:
            prox = c["secao"]
        elif prox:
            c["secao"] = prox
            c["texto"] = re.sub(r"^\[Tabela[^\]]*\]\n", f"[Seção: {prox} | Tabela]\n", c["texto"])
    return [c for c in bons if c["texto"].strip()]


def chunk_texto(texto: str, tamanho: int = 800, overlap: int = 120) -> list[str]:
    texto = (texto or "").strip()
    if not texto:
        return []
    partes, i, n = [], 0, len(texto)
    while i < n:
        partes.append(texto[i : i + tamanho])
        i += max(1, tamanho - overlap)
    return [p for p in partes if p.strip()]


def chunk_csv_linhas(texto: str, cabecalho_repetir: bool = True) -> list[str]:
    """CSV/XLSX exportados: repete o cabeçalho em cada chunk p/ não perder contexto."""
    linhas = [lin for lin in (texto or "").splitlines() if lin.strip()]
    if not linhas:
        return []
    head, corpo = linhas[0], linhas[1:]
    out = []
    for lin in corpo or [""]:
        out.append(f"{head}\n{lin}" if cabecalho_repetir else lin)
    return out
