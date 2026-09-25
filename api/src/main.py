"""FastAPI multi-usuário: auth JWT + chat + threads + ingestão Docling + tickets."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import auth, config, duckdb_store, graph, schemas

app = FastAPI(title="Assistente Suporte TI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    duckdb_store.init_db()
    try:  # warm-up: baixa/carrega pesos p/ não penalizar a 1ª pergunta
        from . import embeddings

        embeddings.modelo()
    except Exception:
        pass


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/auth/register", response_model=schemas.TokenOut)
def register(d: schemas.RegisterIn):
    if duckdb_store.get_user_by_email(d.email):
        raise HTTPException(400, "Email já cadastrado")
    user = duckdb_store.create_user(d.nome, d.email, auth.hash_senha(d.senha), d.role)
    return {"access_token": auth.token(user)}


@app.post("/auth/login", response_model=schemas.TokenOut)
def login(d: schemas.LoginIn):
    user = duckdb_store.get_user_by_email(d.email)
    if not user or not auth.check_senha(d.senha, user["hash"]):
        raise HTTPException(401, "Credenciais inválidas")
    return {"access_token": auth.token(user)}


@app.get("/me")
def me(user: dict = Depends(auth.atual)):
    return {"nome": user["nome"], "email": user["email"], "role": user["role"]}


def _responder_thread(user_id: int, thread_id: str, mensagem: str) -> dict:
    thread = duckdb_store.ensure_thread(user_id, thread_id)
    tid = thread["id"]
    resumo = thread.get("resumo", "") or ""
    historico = duckdb_store.historico_mensagens(user_id, tid)
    out = graph.responder(mensagem, historico=historico, resumo=resumo)
    duckdb_store.log_interacao(user_id, tid, mensagem, out["resposta"], out["escalado"])
    titulo_novo = duckdb_store.maybe_titular(user_id, tid, mensagem)
    # Compactação automática a cada 10 mensagens (5 turnos) da thread
    try:
        total_msgs = duckdb_store.count_turnos(user_id, tid) * 2
        if total_msgs and total_msgs % 10 == 0:
            ultimas = duckdb_store.historico_mensagens(
                user_id, tid, turns=duckdb_store.JANELA_TURNS
            )
            novo = graph.gerar_resumo(resumo, ultimas)
            if novo != resumo:
                duckdb_store.update_resumo(user_id, tid, novo)
    except Exception:
        pass
    return {**out, "thread_id": tid, "titulo_novo": titulo_novo}


def _chat_out(out: dict) -> schemas.ChatOut:
    return schemas.ChatOut(
        resposta=out["resposta"],
        fontes=[
            schemas.Fonte(
                fonte=f.get("fonte", ""), pagina=f.get("pagina"), score=float(f.get("score", 0))
            )
            for f in out["fontes"]
        ],
        escalado=out["escalado"],
        provedor=out.get("provedor", ""),
        thread_id=out.get("thread_id", "default"),
    )


@app.post("/chat", response_model=schemas.ChatOut)
def chat(d: schemas.ChatIn, user: dict = Depends(auth.atual)):
    return _chat_out(_responder_thread(user["id"], d.thread_id, d.mensagem))


@app.post("/chat/stream")
def chat_stream(d: schemas.ChatIn, user: dict = Depends(auth.atual)):
    out = _responder_thread(user["id"], d.thread_id, d.mensagem)

    def gen():
        yield f"data: {out['thread_id']}\n\n"
        for parte in out["resposta"].split("\n"):
            yield f"data: {parte}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/threads", response_model=list[schemas.ThreadOut])
def threads(user: dict = Depends(auth.atual)):
    return [schemas.ThreadOut(**t) for t in duckdb_store.list_threads(user["id"])]


@app.post("/threads", response_model=schemas.ThreadOut)
def criar_thread(d: schemas.ThreadCreateIn | None = None, user: dict = Depends(auth.atual)):
    t = duckdb_store.ensure_thread(user["id"], None)
    if d and d.titulo and d.titulo != "Nova conversa":
        duckdb_store.rename_thread(user["id"], t["id"], d.titulo)
        t = duckdb_store.get_thread(user["id"], t["id"])
    item = {
        "id": t["id"],
        "titulo": t["titulo"],
        "tem_resumo": bool(t["resumo"]),
        "atualizado_em": "",
        "mensagens": 0,
    }
    return schemas.ThreadOut(**item)


@app.get("/threads/{thread_id}", response_model=list[schemas.ThreadMsg])
def thread_msgs(thread_id: str, user: dict = Depends(auth.atual)):
    if not duckdb_store.get_thread(user["id"], thread_id):
        raise HTTPException(404, "Conversa não encontrada")
    return [schemas.ThreadMsg(**m) for m in duckdb_store.mensagens_thread(user["id"], thread_id)]


@app.patch("/threads/{thread_id}", response_model=schemas.ThreadOut)
def renomear_thread(thread_id: str, d: schemas.ThreadRenameIn, user: dict = Depends(auth.atual)):
    if not duckdb_store.get_thread(user["id"], thread_id):
        raise HTTPException(404, "Conversa não encontrada")
    duckdb_store.rename_thread(user["id"], thread_id, d.titulo)
    t = duckdb_store.get_thread(user["id"], thread_id)
    itens = {x["id"]: x for x in duckdb_store.list_threads(user["id"], limit=500)}
    base = itens.get(thread_id, {})
    return schemas.ThreadOut(
        id=t["id"],
        titulo=t["titulo"],
        tem_resumo=bool(t["resumo"]),
        atualizado_em=base.get("atualizado_em", ""),
        mensagens=base.get("mensagens", 0),
    )


@app.delete("/threads/{thread_id}")
def apagar_thread(thread_id: str, user: dict = Depends(auth.atual)):
    if not duckdb_store.get_thread(user["id"], thread_id):
        raise HTTPException(404, "Conversa não encontrada")
    duckdb_store.delete_thread(user["id"], thread_id)
    return {"ok": True}


@app.post("/ingest")
def ingest(files: list[UploadFile] = File(...), user: dict = Depends(auth.admin)):
    from . import chunk as chunk_mod
    from . import ingest_docling as ing
    from . import vector_qdrant as vq

    raw = Path("data/raw")
    proc = Path("data/processed")
    raw.mkdir(parents=True, exist_ok=True)
    total_chunks = 0
    relatorio = []
    for f in files:
        destino = raw / f.filename
        destino.write_bytes(f.file.read())
        info = ing.converter_arquivo(destino, proc)
        doc_id = ""
        if destino.suffix.lower() in {".csv", ".xlsx"}:
            texto = Path(info["md_path"]).read_text(encoding="utf-8")
            partes = [
                {
                    "texto": p,
                    "fonte": f.filename,
                    "pagina": None,
                    "secao": "",
                    "chunk_index": i,
                    "doc_id": f.filename,
                }
                for i, p in enumerate(chunk_mod.chunk_csv_linhas(texto))
            ]
        else:
            from .reingest_v2 import doc_meta

            fonte, doc_id, doc = doc_meta(Path(info["json_path"]))
            fonte = f.filename  # nome real do upload prevalece
            if isinstance(doc, dict) and (doc.get("texts") or doc.get("tables")):
                partes = chunk_mod.chunk_docling(doc, fonte=fonte, doc_id=doc_id)
            else:
                texto = Path(info["md_path"]).read_text(encoding="utf-8")
                partes = [
                    {
                        "texto": p,
                        "fonte": fonte,
                        "pagina": None,
                        "secao": "",
                        "chunk_index": i,
                        "doc_id": doc_id,
                    }
                    for i, p in enumerate(
                        chunk_mod.chunk_texto(texto, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
                    )
                ]
        n = vq.upsert(partes)
        total_chunks += n
        relatorio.append({"arquivo": f.filename, "chunks": n, **info})
    return {"arquivos": len(relatorio), "chunks": total_chunks, "detalhe": relatorio}


@app.get("/tickets")
def tickets(user: dict = Depends(auth.atual)):
    return duckdb_store.ultimas_interacoes(user["id"])
