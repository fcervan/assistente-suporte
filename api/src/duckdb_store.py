"""DuckDB embarcado: users, tickets, threads, interacoes. Writer único serializado."""

from __future__ import annotations

import json
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
              busca VARCHAR DEFAULT '', trechos VARCHAR DEFAULT '[]',
              provedor VARCHAR DEFAULT '',
              criado_em TIMESTAMP DEFAULT current_timestamp)"""
        )
        con.execute("CREATE SEQUENCE IF NOT EXISTS seq_interacoes START 1")
        # Migração aditiva p/ DBs criados antes da observabilidade (post-mortem RAG):
        # busca reescrita + trechos (JSON) + provedor por interação.
        con.execute("ALTER TABLE interacoes ADD COLUMN IF NOT EXISTS busca VARCHAR DEFAULT ''")
        con.execute("ALTER TABLE interacoes ADD COLUMN IF NOT EXISTS trechos VARCHAR DEFAULT '[]'")
        con.execute("ALTER TABLE interacoes ADD COLUMN IF NOT EXISTS provedor VARCHAR DEFAULT ''")
        con.execute(
            """CREATE TABLE IF NOT EXISTS threads(
              id VARCHAR PRIMARY KEY, user_id INTEGER,
              titulo VARCHAR DEFAULT 'Nova conversa', resumo VARCHAR DEFAULT '',
              criado_em TIMESTAMP DEFAULT current_timestamp,
              atualizado_em TIMESTAMP DEFAULT current_timestamp)"""
        )
        # Backfill: threads implícitas de interações antigas (pre-Fase 1)
        try:
            rows = con.execute("SELECT DISTINCT user_id, thread_id FROM interacoes").fetchall()
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


def list_users(limit: int = 200) -> list[dict]:
    with _lock, connect() as con:
        try:
            rows = con.execute(
                "SELECT id,nome,email,role,criado_em FROM users ORDER BY id ASC LIMIT ?",
                [limit],
            ).fetchall()
        except Exception:
            return []
        return [
            {"id": r[0], "nome": r[1], "email": r[2], "role": r[3], "criado_em": str(r[4])}
            for r in rows
        ]


def get_user_by_id(uid: int) -> dict | None:
    with _lock, connect() as con:
        row = con.execute("SELECT id,nome,email,hash,role FROM users WHERE id=?", [uid]).fetchone()
        if not row:
            return None
        return {"id": row[0], "nome": row[1], "email": row[2], "hash": row[3], "role": row[4]}


def update_user(uid: int, nome: str | None = None, role: str | None = None) -> dict | None:
    with _lock, connect() as con:
        row = con.execute("SELECT id FROM users WHERE id=?", [uid]).fetchone()
        if not row:
            return None
        if nome is not None:
            con.execute("UPDATE users SET nome=? WHERE id=?", [nome, uid])
        if role is not None:
            role = "admin" if role == "admin" else "user"
            con.execute("UPDATE users SET role=? WHERE id=?", [role, uid])
    return get_user_by_id(uid)


def set_user_hash(uid: int, hash_: str) -> bool:
    with _lock, connect() as con:
        con.execute("UPDATE users SET hash=? WHERE id=?", [hash_, uid])
        row = con.execute("SELECT id FROM users WHERE id=?", [uid]).fetchone()
        return bool(row)


def delete_user(uid: int) -> None:
    with _lock, connect() as con:
        con.execute("DELETE FROM users WHERE id=?", [uid])


def ensure_admin(email: str, nome: str = "Admin", hash_: str = "") -> dict | None:
    """Garante que um email seja admin (bootstrap fcervan@local)."""
    u = get_user_by_email(email)
    if not u:
        if not hash_:
            return None
        return create_user(nome, email, hash_, "admin")
    if u["role"] != "admin":
        update_user(u["id"], role="admin")
        return get_user_by_id(u["id"])
    return u


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
            {
                "id": r[0],
                "titulo": r[1],
                "tem_resumo": bool(r[2]),
                "atualizado_em": str(r[3]),
                "mensagens": int(r[4]) * 2,
            }
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
        con.execute("DELETE FROM threads WHERE id=? AND user_id=?", [thread_id, user_id])


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


def historico_mensagens(user_id: int, thread_id: str, turns: int = JANELA_TURNS) -> list[dict]:
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


def _compactar_trechos(trechos: list[dict] | None) -> str:
    """Trechos do RAG -> JSON compacto p/ post-mortem (sem o texto integral)."""
    return json.dumps(
        [
            {
                "fonte": t.get("fonte", ""),
                "pagina": t.get("pagina"),
                "secao": str(t.get("secao", ""))[:80],
                "score": t.get("score", 0),
                "dense": t.get("dense", 0),
            }
            for t in (trechos or [])
        ],
        ensure_ascii=False,
    )


def log_interacao(
    user_id: int,
    thread_id: str,
    pergunta: str,
    resposta: str,
    escalado: bool,
    busca: str = "",
    trechos: list[dict] | None = None,
    provedor: str = "",
) -> None:
    with _lock, connect() as con:
        tid = con.execute("SELECT nextval('seq_interacoes')").fetchone()[0]
        con.execute(
            "INSERT INTO interacoes(id,ticket_id,user_id,thread_id,pergunta,resposta,escalado,"
            "busca,trechos,provedor)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                tid,
                None,
                user_id,
                thread_id,
                pergunta,
                resposta,
                escalado,
                busca or "",
                _compactar_trechos(trechos),
                provedor or "",
            ],
        )
        try:
            con.execute(
                "UPDATE threads SET atualizado_em=current_timestamp" " WHERE id=? AND user_id=?",
                [thread_id, user_id],
            )
        except Exception:
            pass


def ultimas_interacoes(user_id: int, limit: int = 20) -> list[dict]:
    with _lock, connect() as con:
        rows = con.execute(
            "SELECT thread_id,pergunta,resposta,escalado,criado_em,busca,trechos,provedor"
            " FROM interacoes"
            " WHERE user_id=? ORDER BY id DESC LIMIT ?",
            [user_id, limit],
        ).fetchall()
        return [
            {
                "thread": r[0],
                "pergunta": r[1],
                "resposta": r[2],
                "escalado": r[3],
                "em": str(r[4]),
                "busca": r[5] or "",
                "trechos": json.loads(r[6] or "[]"),
                "provedor": r[7] or "",
            }
            for r in rows
        ]


def logs_globais(
    limit: int = 100, somente_escalados: bool = False, provedor: str = ""
) -> list[dict]:
    """Visão admin global (observabilidade) com email do autor."""
    with _lock, connect() as con:
        q = (
            "SELECT i.id,i.user_id,u.email,i.thread_id,i.pergunta,i.resposta,"
            " i.escalado,i.provedor,i.busca,i.criado_em"
            " FROM interacoes i LEFT JOIN users u ON u.id=i.user_id"
            " WHERE 1=1"
        )
        params: list = []
        if somente_escalados:
            q += " AND i.escalado=TRUE"
        if provedor:
            q += " AND i.provedor=?"
            params.append(provedor)
        q += " ORDER BY i.id DESC LIMIT ?"
        params.append(limit)
        try:
            rows = con.execute(q, params).fetchall()
        except Exception:
            return []
        return [
            {
                "id": r[0],
                "user_id": r[1] or 0,
                "email": r[2] or "",
                "thread_id": r[3] or "",
                "pergunta": r[4] or "",
                "resposta": r[5] or "",
                "escalado": bool(r[6]),
                "provedor": r[7] or "",
                "busca": r[8] or "",
                "em": str(r[9]),
            }
            for r in rows
        ]


def stats_globais() -> dict:
    with _lock, connect() as con:
        try:
            total = con.execute("SELECT COUNT(*) FROM interacoes").fetchone()[0] or 0
            esc = (
                con.execute("SELECT COUNT(*) FROM interacoes WHERE escalado=TRUE").fetchone()[0]
                or 0
            )
            por_prov = con.execute(
                "SELECT COALESCE(NULLIF(provedor,''),'(vazio)'),COUNT(*)"
                " FROM interacoes GROUP BY 1 ORDER BY 2 DESC"
            ).fetchall()
            por_dia = con.execute(
                "SELECT CAST(criado_em AS DATE),COUNT(*)"
                " FROM interacoes GROUP BY 1 ORDER BY 1 DESC LIMIT 14"
            ).fetchall()
            por_user = (
                con.execute("SELECT COUNT(DISTINCT user_id) FROM interacoes").fetchone()[0] or 0
            )
        except Exception:
            return {
                "total": 0,
                "escalados": 0,
                "pct_escalado": 0,
                "por_provedor": [],
                "por_dia": [],
                "usuarios_ativos": 0,
            }
        return {
            "total": int(total),
            "escalados": int(esc),
            "pct_escalado": round(100 * esc / total, 1) if total else 0,
            "por_provedor": [{"provedor": r[0], "total": int(r[1])} for r in por_prov],
            "por_dia": [{"dia": str(r[0]), "total": int(r[1])} for r in por_dia],
            "usuarios_ativos": int(por_user),
        }
