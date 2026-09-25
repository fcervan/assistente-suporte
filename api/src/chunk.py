"""Chunking: markdown/texto -> lista de chunks (tamanho/overlap do config)."""
from __future__ import annotations


def chunk_texto(texto: str, tamanho: int = 800, overlap: int = 120) -> list[str]:
    texto = (texto or "").strip()
    if not texto:
        return []
    partes, i, n = [], 0, len(texto)
    while i < n:
        partes.append(texto[i: i + tamanho])
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
