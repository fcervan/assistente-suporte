"""FastAPI multi-usuário: auth JWT + chat + ingestão Docling + tickets."""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, UploadFile
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


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/auth/register", response_model=schemas.TokenOut)
def register(d: schemas.RegisterIn):
    if duckdb_store.get_user_by_email(d.email):
        from fastapi import HTTPException

        raise HTTPException(400, "Email já cadastrado")
    user = duckdb_store.create_user(d.nome, d.email, auth.hash_senha(d.senha), d.role)
    return {"access_token": auth.token(user)}


@app.post("/auth/login", response_model=schemas.TokenOut)
def login(d: schemas.LoginIn):
    from fastapi import HTTPException

    user = duckdb_store.get_user_by_email(d.email)
    if not user or not auth.check_senha(d.senha, user["hash"]):
        raise HTTPException(401, "Credenciais inválidas")
    return {"access_token": auth.token(user)}


@app.get("/me")
def me(user: dict = Depends(auth.atual)):
    return {"nome": user["nome"], "email": user["email"], "role": user["role"]}


@app.post("/chat", response_model=schemas.ChatOut)
def chat(d: schemas.ChatIn, user: dict = Depends(auth.atual)):
    out = graph.responder(d.mensagem)
    duckdb_store.log_interacao(
        user["id"], d.thread_id, d.mensagem, out["resposta"], out["escalado"]
    )
    return schemas.ChatOut(
        resposta=out["resposta"],
        fontes=[schemas.Fonte(fonte=f.get("fonte", ""), pagina=f.get("pagina"),
                              score=float(f.get("score", 0))) for f in out["fontes"]],
        escalado=out["escalado"], provedor=out.get("provedor", ""),
    )


@app.post("/chat/stream")
def chat_stream(d: schemas.ChatIn, user: dict = Depends(auth.atual)):
    out = graph.responder(d.mensagem)
    duckdb_store.log_interacao(
        user["id"], d.thread_id, d.mensagem, out["resposta"], out["escalado"]
    )

    def gen():
        for parte in out["resposta"].split("\n"):
            yield f"data: {parte}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


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
        texto = Path(info["md_path"]).read_text(encoding="utf-8")
        if destino.suffix.lower() in {".csv", ".xlsx"}:
            partes = chunk_mod.chunk_csv_linhas(texto)
        else:
            partes = chunk_mod.chunk_texto(texto, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        n = vq.upsert([{"texto": p, "fonte": f.filename} for p in partes])
        total_chunks += n
        relatorio.append({"arquivo": f.filename, "chunks": n, **info})
    return {"arquivos": len(relatorio), "chunks": total_chunks, "detalhe": relatorio}


@app.get("/tickets")
def tickets(user: dict = Depends(auth.atual)):
    return duckdb_store.ultimas_interacoes(user["id"])
