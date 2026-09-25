# Assistente de Suporte Técnico (TI/software PT-BR)

RAG multi-usuário: **FastAPI (`:8002`) + React (`:5175`) + Qdrant (`:6333/6334`) + DuckDB embarcado (pip)**.

Decisões travadas:
- Ingestão **só Docling** (PDF/DOCX/XLSX/CSV/HTML/XML → `.md` + `.json` em `data/processed/`).
- DuckDB via `pip` dentro do container `api` + volume `./data/duckdb` (sem container próprio; Postgres só na v2 se precisar).
- Fallback LLM: **Groq → Ollama Cloud → OpenRouter** (`api/src/llm_client.py`, reuso do avaliador-vendas).
- Frontend no guia **Pastel 3D** (lavanda `#9A89D4`, fundo `#FAEBE6`, relevo tátil, `web/src/tokens.css`).

## Subir

```bash
cp .env.example .env   # preencher GROQ_API_KEY (ou Ollama/OpenRouter) + JWT_SECRET
docker compose up --build
# web: http://localhost:5175 | api: http://localhost:8002/docs | qdrant: http://localhost:6333/dashboard
```

## Estrutura

```
api/src: config, llm_client, auth(JWT), duckdb_store, ingest_docling, chunk,
         embeddings, vector_qdrant, graph(LangGraph), schemas, main(FastAPI)
web/src: tokens.css, api.js, pages/Login,Chat,Ingest,Admin
notebooks: 01_assistente_suporte.ipynb (demo) + 02_uso_colab.ipynb (cliente da API)
tests: auth, chunk, graph, llm_fallback
```

## Fluxo

Upload (admin) → Docling → chunk → embeddings PT → Qdrant (denso+BM25) |
Chat → triagem → retrieve híbrido → grade → gerar c/ citação → escalate → log DuckDB.
