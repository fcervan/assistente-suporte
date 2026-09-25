"""Eval dourado do RAG (roda DENTRO do container api, com Qdrant+embeddings).

Uso: docker compose exec api python -m src.eval_douradas [--csv tests/douradas.csv]
Critério de aceite Fase 4: hit@4 >= 12/15.
"""
from __future__ import annotations

import argparse
import csv
import sys
import unicodedata


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.lower()


def carregar(csv_path: str) -> list[tuple[str, list[str]]]:
    with open(csv_path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))
    return [(r["pergunta"], [k.strip() for k in r["keywords"].split("|") if k.strip()])
            for r in rows]


def avaliar(csv_path: str, top_k: int = 4) -> int:
    from . import vector_qdrant

    casos = carregar(csv_path)
    hits = 0
    for i, (pergunta, kws) in enumerate(casos, 1):
        trechos = vector_qdrant.buscar(pergunta, top_k=top_k)
        blob = norm(" ".join(f"{t.get('secao','')} {t.get('texto','')}" for t in trechos))
        ok_kw = [k for k in kws if norm(k) in blob]
        ok = bool(ok_kw)
        hits += ok
        secoes = " | ".join(f"{t.get('secao','?')[:45]} p.{t.get('pagina')}" for t in trechos)
        print(f"[{'HIT ' if ok else 'MISS'}] Q{i:02d} {pergunta[:70]}")
        print(f"       kw={ok_kw or '-'} :: {secoes}", flush=True)
    print(f"[eval] hit@{top_k}: {hits}/{len(casos)}")
    return 0 if hits >= 12 else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="tests/douradas.csv")
    args = ap.parse_args()
    sys.exit(avaliar(args.csv))


if __name__ == "__main__":
    main()
