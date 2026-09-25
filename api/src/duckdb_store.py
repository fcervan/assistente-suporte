"""DuckDB embarcado: users, tickets, threads, interacoes. Writer único serializado."""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

import duckdb

from . import config

_lock = threading.Lock()

TITULO_PADRAO = "Nova conversa"
JANELA_TURNS = 5  # 5 turnos = 10 mensagens (user+bot) no prompt


def connect():
    Path(config.DUCKDB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(config.DUCKDB_PATH)


def init_db() -> None:
    with _lock, connect() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS users(
              id INTEGER PRIMARY KEY, nome VARCHAR, email VARCHAR UNIQUE,
              hash VARCHAR, role VARCHAR DEFAULT 'user',
              criado_em TIMESTAMP DEFAULT current_timestamp)"""
        )
        con.execute("CREATE SEQUENCE IF NOT EXISTS seq_users START 1")
        con.execute(
            """CREATE TABLE IF NOT EXISTS tickets(
              id INTEGER PRIMARY KEY, user_id INTEGER, titulo VARCHAR,
              status VARCHAR DEFAULT 'aberto',
              criado_em TIMESTAMP DEFAULT current_timestamp)"""
        )
        con.execute("CREATE SEQUENCE IF NOT EXISTS seq_tickets START 1")
        con.execute(
            """CREATE TABLE IF NOT EXISTS interacoes(
              id INTEGER PRIMARY KEY, ticket_id INTEGER, user_id INTEGER,
              thread_id VARCHAR, pergunta VARCHAR, resposta VARCHAR,
              escalado BOOLEAN DEFAULT FALSE,
              criado_em TIMESTAMP DEFAULT current_timestamp)"""
        )
        con.execute("CREATE SEQUENCE IF NOT EXISTS seq_interacoes START 1")
        con.execute(
            """CREATE TABLE IF NOT EXISTS threads(
              id VARCHAR PRIMARY KEY, user_id INTEGER,
              titulo VARCHAR DEFAULT 'Nova conversa', resumo VARCHAR DEFAULT '',
              criado_em TIMESTAMP DEFAULT current_timestamp,
              atualizado_em TIMESTAMP DEFAULT current_timestamp)"""
        )
        # Backfill: threads implícitas de interações antigas (pre-Fase 1)
        try:
            rows = con.execute(
                "SELECT DISTINCT user_id, thread_id FROM interacoes"
            ).fetchall()
            for uid, tid in rows:
                tid = tid or "default"
                existe = con.execute(
                    "SELECT 1 FROM threads WHERE id=? AND user_id=?", [tid, uid]
                ).fetchone()
                if not existe:
                    primeira = con.execute(
                        "SELECT pergunta FROM interacoes WHERE user_id=? AND thread_id=?"
                        " ORDER BY id ASC LIMIT 1",
                        [uid, tid],
                    ).fetchone()
                    titulo = titulo_de((primeira[0] if primeira else "") or "")
                    con.execute(
                        "INSERT INTO threads(id,user_id,titulo) VALUES (?,?,?)",
                        [tid, uid, titulo],
                    )
        except Exception:
            pass


def create_user(nome: str, email: str, hash_: str, role: str = "user") -> dict:
    with _lock, connect() as con:
        uid = con.execute("SELECT nextval('seq_users')").fetchone()[0]
        con.execute(
            "INSERT INTO users(id,nome,email,hash,role) VALUES (?,?,?,?,?)",
            [uid, nome, email, hash_, role],
        )
        return {"id": uid, "nome": nome, "email": email, "role": role}


def get_user_by_email(email: str) -> dict | None:
    with _lock, connect() as con:
        row = con.execute(
            "SELECT id,nome,email,hash,role FROM users WHERE email=?", [email]
        ).fetchone()
        if not row:
            return None
        return {"id": row[0], "nome": row[1], "email": row[2], "hash": row[3], "role": row[4]}


def titulo_de(pergunta: str, limite: int = 60) -> str:
    t = " ".join((pergunta or "").split())[:limite].strip()
    return t or TITULO_PADRAO


def ensure_thread(user_id: int, thread_id: str | None) -> dict:
    """Garante thread do usuário; cria com uuid quando vazia/inexistente."""
    tid = (thread_id or "").strip() or str(uuid.uuid4().hex[:12])
    with _lock, connect() as con:
        row = con.execute(
            "SELECT id,titulo,resumo FROM threads WHERE id=? AND user_id=?",
            [tid, user_id],
        ).fetchone()
        if row:
            return {"id": row[0], "titulo": row[1], "resumo": row[2] or ""}
        con.execute(
            "INSERT INTO threads(id,user_id,titulo) VALUES (?,?,?)",
            [tid, user_id, TITULO_PADRAO],
        )
        return {"id": tid, "titulo": TITULO_PADRAO, "resumo": ""}


def list_threads(user_id: int, limit: int = 50) -> list[dict]:
    with _lock, connect() as con:
        try:
            rows = con.execute(
                "SELECT t.id,t.titulo,t.resumo,t.atualizado_em,"
                " (SELECT COUNT(*) FROM interacoes i"
                "  WHERE i.user_id=t.user_id AND i.thread_id=t.id) AS n"
                " FROM threads t WHERE t.user_id=?"
                " ORDER BY t.atualizado_em DESC LIMIT ?",
                [user_id, limit],
            ).fetchall()
        except Exception:
            return []
        return [
            {"id": r[0], "titulo": r[1], "tem_resumo": bool(r[2]),
             "atualizado_em": str(r[3]), "mensagens": int(r[4]) * 2}
            for r in rows
        ]


def get_thread(user_id: int, thread_id: str) -> dict | None:
    with _lock, connect() as con:
        try:
            row = con.execute(
                "SELECT id,titulo,resumo FROM threads WHERE id=? AND user_id=?",
                [thread_id, user_id],
            ).fetchone()
        except Exception:
            return None
        if not row:
            return None
        return {"id": row[0], "titulo": row[1], "resumo": row[2] or ""}


def rename_thread(user_id: int, thread_id: str, titulo: str) -> bool:
    titulo = " ".join((titulo or "").split())[:80] or TITULO_PADRAO
    with _lock, connect() as con:
        con.execute(
            "UPDATE threads SET titulo=?, atualizado_em=current_timestamp"
            " WHERE id=? AND user_id=?",
            [titulo, thread_id, user_id],
        )
        row = con.execute(
            "SELECT id FROM threads WHERE id=? AND user_id=?", [thread_id, user_id]
        ).fetchone()
        return bool(row)


def delete_thread(user_id: int, thread_id: str) -> None:
    with _lock, connect() as con:
        con.execute(
            "DELETE FROM interacoes WHERE user_id=? AND thread_id=?",
            [user_id, thread_id],
        )
        con.execute(
            "DELETE FROM threads WHERE id=? AND user_id=?", [thread_id, user_id]
        )


def get_resumo(user_id: int, thread_id: str) -> str:
    t = get_thread(user_id, thread_id)
    return (t or {}).get("resumo", "")


def update_resumo(user_id: int, thread_id: str, resumo: str) -> None:
    with _lock, connect() as con:
        con.execute(
            "UPDATE threads SET resumo=?, atualizado_em=current_timestamp"
            " WHERE id=? AND user_id=?",
            [(resumo or "")[:4000], thread_id, user_id],
        )


def maybe_titular(user_id: int, thread_id: str, pergunta: str) -> str | None:
    """Define título a partir da 1ª pergunta quando ainda é o padrão."""
    with _lock, connect() as con:
        row = con.execute(
            "SELECT titulo FROM threads WHERE id=? AND user_id=?",
            [thread_id, user_id],
        ).fetchone()
        if row and (row[0] or "") in ("", TITULO_PADRAO):
            titulo = titulo_de(pergunta)
            con.execute(
                "UPDATE threads SET titulo=? WHERE id=? AND user_id=?",
                [titulo, thread_id, user_id],
            )
            return titulo
        return None


def count_turnos(user_id: int, thread_id: str) -> int:
    with _lock, connect() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM interacoes WHERE user_id=? AND thread_id=?",
            [user_id, thread_id],
        ).fetchone()
        return int(row[0]) if row else 0


def historico_mensagens(user_id: int, thread_id: str,
                        turns: int = JANELA_TURNS) -> list[dict]:
    """Últimos N turnos como [{role, content}] ordenado ASC (role=user|assistant)."""
    with _lock, connect() as con:
        rows = con.execute(
            "SELECT pergunta,resposta FROM interacoes"
            " WHERE user_id=? AND thread_id=? ORDER BY id DESC LIMIT ?",
            [user_id, thread_id, turns],
        ).fetchall()
    msgs: list[dict] = []
    for pergunta, resposta in reversed(rows):
        if pergunta:
            msgs.append({"role": "user", "content": pergunta})
        if resposta:
            msgs.append({"role": "assistant", "content": resposta})
    return msgs


def mensagens_thread(user_id: int, thread_id: str, limit: int = 100) -> list[dict]:
    with _lock, connect() as con:
        rows = con.execute(
            "SELECT pergunta,resposta,escalado,criado_em FROM interacoes"
            " WHERE user_id=? AND thread_id=? ORDER BY id ASC LIMIT ?",
            [user_id, thread_id, limit],
        ).fetchall()
        return [
            {"pergunta": r[0], "resposta": r[1], "escalado": bool(r[2]), "em": str(r[3])}
            for r in rows
        ]


def log_interacao(user_id: int, thread_id: str, pergunta: str,
                  resposta: str, escalado: bool) -> None:
    with _lock, connect() as con:
        tid = con.execute("SELECT nextval('seq_interacoes')").fetchone()[0]
        con.execute(
            "INSERT INTO interacoes(id,ticket_id,user_id,thread_id,pergunta,resposta,escalado)"
            " VALUES (?,?,?,?,?,?,?)",
            [tid, None, user_id, thread_id, pergunta, resposta, escalado],
        )
        try:
            con.execute(
                "UPDATE threads SET atualizado_em=current_timestamp"
                " WHERE id=? AND user_id=?",
                [thread_id, user_id],
            )
        except Exception:
            pass


def ultimas_interacoes(user_id: int, limit: int = 20) -> list[dict]:
    with _lock, connect() as con:
        rows = con.execute(
            "SELECT thread_id,pergunta,resposta,escalado,criado_em FROM interacoes"
            " WHERE user_id=? ORDER BY id DESC LIMIT ?",
            [user_id, limit],
        ).fetchall()
        return [
            {"thread": r[0], "pergunta": r[1], "resposta": r[2], "escalado": r[3], "em": str(r[4])}
            for r in rows
        ]
