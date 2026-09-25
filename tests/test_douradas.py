"""Valida o CSV dourado localmente (o retrieval live roda no container)."""

import csv
from pathlib import Path


def test_douradas_bem_formadas():
    csv_path = Path(__file__).parent / "douradas.csv"
    with open(csv_path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))
    assert len(rows) == 16, f"esperado 16, achado {len(rows)}"
    for r in rows:
        assert r["pergunta"].strip(), "pergunta vazia"
        kws = [k.strip() for k in r["keywords"].split("|") if k.strip()]
        assert kws, f"sem keywords: {r['pergunta']}"
