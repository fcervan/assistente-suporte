"""DuckDB embarcado: users, tickets, interacoes. Writer único serializado."""
from __future__ import annotations

import threading
from pathlib import Path

import duckdb

from . import config

_lock = threading.Lock()


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


def log_interacao(user_id: int, thread_id: str, pergunta: str,
                  resposta: str, escalado: bool) -> None:
    with _lock, connect() as con:
        tid = con.execute("SELECT nextval('seq_interacoes')").fetchone()[0]
        con.execute(
            "INSERT INTO interacoes(id,ticket_id,user_id,thread_id,pergunta,resposta,escalado)"
            " VALUES (?,?,?,?,?,?,?)",
            [tid, None, user_id, thread_id, pergunta, resposta, escalado],
        )


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
