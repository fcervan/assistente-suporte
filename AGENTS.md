# Assistente de Suporte Técnico (TI/software PT-BR)

RAG multi-usuário com base de conhecimento ingerida via Docling. Stack: **FastAPI + React + Qdrant + DuckDB embarcado + LangGraph**.

## Arquitetura

Monorepo com dois apps + infra (tudo via `docker-compose.yml`):

- **`api/`** — Backend FastAPI (Python 3.12) em `suporte-api:8002`. Auth JWT local, ingestão Docling, RAG híbrido, grafo LangGraph.
- **`web/`** — Frontend React 18 + Vite 6 (JSX, sem Tailwind, CSS próprio em `src/tokens.css`). Servido por nginx em `suporte-web:5175`.
- **`qdrant`** — `qdrant/qdrant:latest` em `6333/6334`, volume `qdrant_storage`. Coleção `suporte_ti` (vetor denso + payload fonte/pagina).
- **DuckDB** — embarcado via `pip` **dentro do container `api`** (`/app/data/duckdb/tickets.duckdb`, volume `./data`). Não existe "DuckDB server" — container separado não dá concorrência. Slot comentado para `postgres:5432` na v2 se a escrita concorrente estourar.

### Fluxo

```
Upload (admin) → Docling → data/processed (.md+.json) → chunk → embeddings PT → Qdrant
Chat → triagem → retrieve híbrido (denso+BM25/RRF) → grade → gerar c/ citação → escalate → log DuckDB
```

### LLM fallback (`api/src/llm_client.py`)

**Groq → Ollama Cloud → OpenRouter** (mesmo padrão do avaliador-vendas). Chaves via `.env` (`GROQ_API_KEY`, `OLLAMA_CLOUD_API_KEY`, `OPENROUTER_API_KEY`) — **nunca versionar o `.env`**. Modelos default via `GROQ_MODEL`, `OLLAMA_CLOUD_MODEL`, `OPENROUTER_MODEL`.

## Autonomia operacional (instrução permanente do usuário)

Ao terminar um trabalho: pode buildar/testar/rodar sem pedir (`docker compose up -d --build`, `pytest`, `ruff`, `npm run build`). Nunca fazer `git add/commit/push` sem confirmação explícita — perguntar primeiro e, quando confirmado, mostrar a saída do push.

Toda mudança em `api/src` ou `web/src` (telas, endpoints, funções, contagens, estrutura) exige verificar e atualizar o `README.md` antes de encerrar — ele precisa refletir tudo que a aplicação tem.

## Comandos

```bash
cp .env.example .env   # preencher chaves + JWT_SECRET
docker compose up -d --build   # primeira vez (api ~7GB: torch+docling; demora)
docker compose up -d           # subidas seguintes
docker compose down            # dados persistem (volumes)
docker compose logs api|web|qdrant
docker compose up -d --build web   # rebuild só do frontend (~1 min)

# Testes backend (pip install -r requirements-dev.txt; duckdb incluso)
python3 -m pytest tests/ -q
python3 -m ruff check api/src tests
```

Portas (verificadas livres no host): `8002` api, `5175` web, `6333/6334` qdrant.

## Endpoints principais

- `GET /health`
- `POST /auth/register` `{nome, email, senha, role=user|admin}` → `{access_token}` (primeiro usuário: registre com `role=admin`)
- `POST /auth/login` → `{access_token}`
- `GET /me` — perfil
- `POST /chat` `{mensagem, thread_id}` → `{resposta, fontes[{fonte,pagina,score}], escalado, provedor}`
- `POST /chat/stream` — SSE
- `POST /ingest` (só admin, multipart) — PDF/DOCX/PPTX/XLSX/CSV/HTML/XML/TXT/MD → `{arquivos, chunks, detalhe}`
- `GET /tickets` — últimas interações do usuário
- `GET/POST /users`, `PATCH/DELETE /users/{id}` (só admin; bloqueia auto-remoção e auto-rebaixamento)
- `GET /admin/logs`, `GET /admin/stats` (só admin — observabilidade global)

## Banco (DuckDB — `api/src/duckdb_store.py`)

Tabelas: `users(id,nome,email unique,hash,role)`, `tickets`, `interacoes(user_id,thread_id,pergunta,resposta,escalado)`. Writer único com `threading.Lock`. Sequences `seq_users`, `seq_tickets`, `seq_interacoes`.

## Frontend (`web/src`)

- `tokens.css` — tema **dark copiado do app-prospeccao/dashboard** (env `#0c0e12`, azul `#5fa3d9`, champanhe `#d8bf8e`, grain, `.stage/.panel/.card/.recessed/.btn-primary/.badge-*/.nav-item`, mobile com hamburger). Pastel descartado.
- `App.jsx` — shell `stage > panel fluido (max 1760px) > sidebar 240px/64px colapsada + main` (espelha `Layout.tsx` do prospecção).
- `pages/`: `Login` (labels E-MAIL/SENHA + `.recessed`), `Chat` (composer textarea fixo + autoscroll + tooltip título + data/hora), `Ingest` (admin, dropzone arrastar+clicar), `Admin` (tickets), `Usuarios` (admin CRUD), `Observabilidade` (admin logs+stats).
- `api.js` — `VITE_API_URL` (default `http://localhost:8002`).

## Notebooks

- `notebooks/01_assistente_suporte.ipynb` — demo didática (getpass, sem versionar chave).
- `notebooks/02_uso_colab.ipynb` — cliente da API via `requests` (1-clique Colab).

## Armadilhas já resolvidas (não reintroduzir)

1. `passlib 1.7.4 + bcrypt>=4.1` quebra o hash (`72 bytes`) → `bcrypt==4.0.1` pinado em `api/requirements.txt`.
2. Imagem `python:3.12-slim` sem libs do OpenCV (`libxcb.so.1`) → `Dockerfile` instala `libgl1 libxcb1 libglib2.0-0 libsm6 libxext6 libxrender1`.
3. `DoclingDocument` não tem `export_to_json` → usar `json.dumps(doc.export_to_dict())`.
4. Chaves retornadas pelos nodes **precisam existir no `State`** do LangGraph (ex: `provedor: str`) ou são descartadas em silêncio.
5. `web/vite.config.js` **exige `@vitejs/plugin-react`** — sem ele o JSX compila em modo clássico e dá `React is not defined` com tela em branco.
6. Screenshot headless com `--virtual-time-budget` congela CSS animations no frame 0 (parece tela vazia) — usar `--timeout` para captura fiel.

## Deploy / acesso local

- Web: http://localhost:5175 · API docs: http://localhost:8002/docs · Qdrant: http://localhost:6333/dashboard
- Usuário admin local: `fcervan@local` / `123456` (criado via `/auth/register` com `role=admin`).
- Base inicial: `manual-smartlabel.pdf` (Manual API SmartLabel v2.1, 145 chunks, 9 tabelas).
