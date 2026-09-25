"""Fase 1+2 (bugs): threads via endpoints + Nova conversa de verdade."""

import sys
import types

import pytest
from fastapi import HTTPException
from src import auth, config, main, schemas
from src import duckdb_store as store


def _stub_src(monkeypatch, name, mod):
    """Stub que vale p/ `from . import x` (sys.modules + atributo do pacote)."""
    import src as _pkg

    monkeypatch.setitem(sys.modules, f"src.{name}", mod)
    monkeypatch.setattr(_pkg, name, mod, raising=False)


@pytest.fixture()
def user(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules, "src.vector_qdrant", types.SimpleNamespace(buscar=lambda *a, **k: [])
    )
    monkeypatch.setattr(config, "DUCKDB_PATH", str(tmp_path / "api.duckdb"))
    store.init_db()
    return store.create_user("T", "t@t.t", auth.hash_senha("123456"), "user")


def test_post_threads_cria_id_unico(user):
    a = main.criar_thread(None, user)
    b = main.criar_thread(None, user)
    assert a.id and b.id and a.id != b.id


def test_chat_thread_vazia_cria_nova_e_reusa(user):
    r1 = main.chat(schemas.ChatIn(mensagem="oi", thread_id=""), user)
    assert r1.thread_id and r1.thread_id != "default"  # não cai no default
    r2 = main.chat(schemas.ChatIn(mensagem="de novo", thread_id=r1.thread_id), user)
    assert r2.thread_id == r1.thread_id  # continua na mesma
    msgs = main.thread_msgs(r1.thread_id, user)
    assert [m.pergunta for m in msgs] == ["oi", "de novo"]


def test_threads_crud_http(user):
    t = main.criar_thread(None, user)
    assert any(x.id == t.id for x in main.threads(user))
    r = main.renomear_thread(t.id, schemas.ThreadRenameIn(titulo="Minha VPN"), user)
    assert r.titulo == "Minha VPN"
    assert main.apagar_thread(t.id, user) == {"ok": True}
    with pytest.raises(HTTPException):
        main.thread_msgs(t.id, user)
