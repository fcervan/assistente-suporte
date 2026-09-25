"""Reimportação total v2: wipe da coleção + chunk_docling de processed/*.json.

Uso (dentro do container api):
    python -m src.reingest_v2 [--no-wipe] [--proc data/processed]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def doc_meta(json_path: Path) -> tuple[str, str, dict | str]:
    """Retorna (fonte, doc_id) a partir do JSON do Docling."""
    try:
        doc = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return json_path.stem, hashlib.sha1(str(json_path).encode()).hexdigest()[:16]
    origin = doc.get("origin") or {}
    fonte = origin.get("filename") or f"{json_path.stem}.pdf"
    bhash = origin.get("binary_hash")
    doc_id = str(bhash) if bhash else hashlib.sha1(json_path.stem.encode()).hexdigest()[:16]
    return fonte, doc_id, doc


def reimportar(proc_dir: str = "data/processed", wipe: bool = True) -> dict:
    from . import chunk as chunk_mod
    from . import vector_qdrant as vq

    proc = Path(proc_dir)
    arquivos = sorted(proc.glob("*.json"))
    if wipe:
        print(f"[reingest] WIPE da coleção + reimportação de {len(arquivos)} json(s)", flush=True)
        vq.wipe_colecao()
    total, detalhe = 0, []
    for jp in arquivos:
        fonte, doc_id, doc = doc_meta(jp)
        if isinstance(doc, dict) and (doc.get("texts") or doc.get("tables")):
            partes = chunk_mod.chunk_docling(doc, fonte=fonte, doc_id=doc_id)
        else:  # fallback: .md legado fatiado simples
            md = jp.with_suffix(".md")
            texto = md.read_text(encoding="utf-8") if md.exists() else ""
            partes = [
                {
                    "texto": p,
                    "fonte": fonte,
                    "pagina": None,
                    "secao": "",
                    "chunk_index": i,
                    "doc_id": doc_id,
                }
                for i, p in enumerate(chunk_mod.chunk_texto(texto, 800, 120))
            ]
        n = vq.upsert(partes)
        total += n
        detalhe.append({"arquivo": jp.name, "fonte": fonte, "chunks": n})
        print(f"[reingest] {jp.name} -> {n} chunks (fonte={fonte})", flush=True)
    return {"arquivos": len(detalhe), "chunks": total, "detalhe": detalhe}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc", default="data/processed")
    ap.add_argument("--no-wipe", action="store_true")
    args = ap.parse_args()
    rel = reimportar(args.proc, wipe=not args.no_wipe)
    print(f"[reingest] OK: {rel['arquivos']} arquivo(s), {rel['chunks']} chunks")


if __name__ == "__main__":
    sys.exit(main())
