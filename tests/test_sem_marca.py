"""Blindagem: nenhuma referência a marca/produto real no repo.

A demonstração usa apenas a base fictícia (manual-acme-ficticio.pdf, 100%
inventado). Este teste quebra o CI se o nome da marca real voltar a aparecer
em código, testes, docs ou notebooks — ou se algum arquivo com esse nome for
adicionado em data/.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Montado em partes p/ o próprio teste não conter o termo literal.
BANIDO = "smart" + "label"
ARQUIVOS_EXCLUIDOS = {Path(__file__).name}
# Gerados/build: o fonte já foi limpo; o bundle é regenerado no build da web.
PASTAS_EXCLUIDAS = {"dist", "__pycache__", "node_modules", ".pytest_cache", ".ruff_cache"}

EXTENSOES = {
    ".py",
    ".jsx",
    ".js",
    ".md",
    ".csv",
    ".txt",
    ".json",
    ".ipynb",
    ".yml",
    ".yaml",
    ".toml",
}


def _varrer():
    achados = []
    for base in (ROOT / "api", ROOT / "web", ROOT / "tests", ROOT / "notebooks"):
        if not base.exists():
            continue
        for arq in sorted(base.rglob("*")):
            if not arq.is_file() or arq.name in ARQUIVOS_EXCLUIDOS:
                continue
            if PASTAS_EXCLUIDAS & set(arq.parts):
                continue
            if arq.suffix.lower() not in EXTENSOES:
                continue
            try:
                texto = arq.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if BANIDO in texto.lower():
                achados.append(str(arq.relative_to(ROOT)))
    for base in (ROOT / "README.md", ROOT / "AGENTS.md"):
        if base.exists() and BANIDO in base.read_text(encoding="utf-8", errors="ignore").lower():
            achados.append(base.name)
    for pasta in (ROOT / "data",):
        if pasta.exists():
            for arq in pasta.rglob("*"):
                if BANIDO in arq.name.lower():
                    achados.append(str(arq.relative_to(ROOT)))
    return achados


def test_sem_marca_real():
    assert _varrer() == [], f"referência a marca real encontrada: {_varrer()}"
