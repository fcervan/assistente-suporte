"""Ingestão SÓ com Docling: raw -> processed (.md + .json)."""
from __future__ import annotations

from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".html", ".htm", ".xml", ".txt", ".md"}


def converter_arquivo(origem: Path, destino_dir: Path) -> dict:
    """Converte 1 arquivo via Docling. Retorna {md_path, json_path, tabelas}."""
    import json

    from docling.document_converter import DocumentConverter

    destino_dir.mkdir(parents=True, exist_ok=True)
    conv = DocumentConverter()
    result = conv.convert(str(origem))
    doc = result.document
    base = origem.stem
    md_path = destino_dir / f"{base}.md"
    json_path = destino_dir / f"{base}.json"
    md_path.write_text(doc.export_to_markdown(), encoding="utf-8")
    json_path.write_text(json.dumps(doc.export_to_dict(), ensure_ascii=False), encoding="utf-8")
    try:
        tabelas = len(doc.tables)
    except Exception:
        tabelas = 0
    return {"md_path": str(md_path), "json_path": str(json_path), "tabelas": tabelas}


def ingerir_pasta(raw_dir: str | Path = "data/raw",
                  out_dir: str | Path = "data/processed") -> list[dict]:
    raw, out = Path(raw_dir), Path(out_dir)
    feitos = []
    for arq in sorted(raw.iterdir()):
        if arq.is_file() and arq.suffix.lower() in SUPPORTED:
            info = converter_arquivo(arq, out)
            feitos.append({"arquivo": arq.name, **info})
    return feitos
