"""Cliente HTTP do docling-service: raw -> processed (.md + .json).

O Docling não roda mais nesta API. O serviço externo recebe o arquivo e
devolve {document, markdown, tabelas}; aqui persistimos o resultado para
manter o chunking/reingest atuais.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

SUPPORTED = {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".html", ".htm", ".xml", ".txt", ".md"}


class DoclingError(RuntimeError):
    """Falha ao falar com o docling-service."""


def converter_arquivo(origem: Path, destino_dir: Path) -> dict:
    """Envia 1 arquivo ao docling-service. Retorna {md_path, json_path, tabelas}."""
    from . import config

    destino_dir.mkdir(parents=True, exist_ok=True)
    url = f"{config.DOCLING_URL.rstrip('/')}/v1/convert"
    headers = {}
    if config.DOCLING_API_KEY:
        headers["X-API-Key"] = config.DOCLING_API_KEY

    try:
        with origem.open("rb") as fh:
            resp = httpx.post(
                url,
                headers=headers,
                files={"file": (origem.name, fh, "application/octet-stream")},
                timeout=config.DOCLING_TIMEOUT,
            )
    except httpx.TimeoutException as exc:
        raise DoclingError("docling-service excedeu o tempo de resposta") from exc
    except httpx.HTTPError as exc:
        raise DoclingError("docling-service indisponível") from exc

    if resp.status_code != 200:
        raise DoclingError(f"docling-service respondeu HTTP {resp.status_code}")
    try:
        dados = resp.json()
    except ValueError as exc:
        raise DoclingError("docling-service devolveu uma resposta inválida") from exc

    documento = dados.get("document")
    if not isinstance(documento, dict):
        raise DoclingError("docling-service não devolveu o campo 'document'")

    base = origem.stem
    md_path = destino_dir / f"{base}.md"
    json_path = destino_dir / f"{base}.json"
    md_path.write_text(str(dados.get("markdown") or ""), encoding="utf-8")
    json_path.write_text(json.dumps(documento, ensure_ascii=False), encoding="utf-8")
    try:
        tabelas = int(dados.get("tabelas") or 0)
    except (TypeError, ValueError):
        tabelas = 0
    return {"md_path": str(md_path), "json_path": str(json_path), "tabelas": tabelas}


def ingerir_pasta(
    raw_dir: str | Path = "data/raw", out_dir: str | Path = "data/processed"
) -> list[dict]:
    raw, out = Path(raw_dir), Path(out_dir)
    feitos = []
    for arq in sorted(raw.iterdir()):
        if arq.is_file() and arq.suffix.lower() in SUPPORTED:
            info = converter_arquivo(arq, out)
            feitos.append({"arquivo": arq.name, **info})
    return feitos
