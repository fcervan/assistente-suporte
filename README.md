# Assistente de Suporte Técnico com IA

[![CI](https://github.com/fcervan/assistente-suporte/actions/workflows/ci.yml/badge.svg)](https://github.com/fcervan/assistente-suporte/actions)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![Cobertura 100%](https://img.shields.io/badge/coverage-100%25-brightgreen)](tests/)
[![Licença MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fcervan/assistente-suporte/blob/main/notebooks/02_uso_colab.ipynb)
[![Docker](https://img.shields.io/badge/docker-compose--ready-blue)](docker-compose.yml)
[![LangGraph](https://img.shields.io/badge/langgraph-orchestration-purple)](api/src/graph.py)
[![FastAPI](https://img.shields.io/badge/fastapi-%3A8002-teal)](api/src/main.py)
[![React 18](https://img.shields.io/badge/react-18-61dafb)](web/src/)
[![Docling](https://img.shields.io/badge/docling-ingest-orange)](https://github.com/docling-project/docling)

RAG multiusuário de suporte técnico de TI (PT-BR): o usuário envia documentos
(PDF/DOCX/XLSX…), conversa num chat com **memória e histórico persistente**, e recebe
respostas **grounded na base** — com citação de fonte e página — ou escalação honesta
ao time humano quando não há base suficiente.

Diferenciais técnicos: chunking por **estrutura do documento** (seção/página/tabela,
145 → 55 chunks), RAG **híbrido denso + BM25 com stemming PT** (fusão RRF por conteúdo),
memória conversacional (últimas 10 mensagens + **resumo compactado a cada 10**),
threads estilo ChatGPT (criar/continuar/renomear/apagar, tooltip com título cheio e
data/hora `dd/mm/aaaa às hh:mm`), chat padrão mercado (textarea fixa, autoscroll),
gestão de **usuários com perfis user/admin** e tela de **observabilidade**
(log global + métricas: total, % escalado, por provedor) — além do **eval dourado 15/15**.

## Demonstração

Eval dourado sobre o Manual da API SmartLabel (`tests/douradas.csv`): 16 perguntas
reais (autenticação, método Registrar, responses 200/206/400/401, impressão de
etiquetas, envio em lote…) — **hit@4 em 16/16** após o chunking v2 (antes: 10/15,
com direito a alucinação: um “sim, pode enviar pedido a pedido” confiante e errado,
hoje respondido corretamente como proibido, com citação).

| # | Pergunta | Resultado |
|---|---|---|
| 1 | Como funciona a autenticação? | ✅ seção Autenticação, p. 13 |
| 2 | O que é o método Registrar? | ✅ seções 3, 4 e 4.2 |
| 3 | O que é o campo clienteCodigo? | ✅ tabela 4.2 (parte 3/4), p. 8 |
| 4–7 | Responses 200 / 206 / 400 / 401 | ✅ exemplos, pp. 18–20 |
| 8 | Como imprimir as etiquetas? | ✅ Modelo de etiqueta, p. 21 |
| 9 | Disponibilidade da API? | ✅ 24h/7d, seção 1.2 |
| 10 | Posso enviar pedidos um a um? | ✅ “proibido”, seção 1.3 |
| 11–15 | Testes, falhas, acesso, exemplo, conceito | ✅ |
| 16 | Posso enviar mais de um pedido por request? | ✅ “um ou mais volumes (encomendas)”, seção 4 |

> 📸 Prints do chat e da sidebar de conversas entram aqui em breve (`docs/demo-chat.png`, `docs/demo-threads.png`).

## Como funciona

Grafo LangGraph com memória (`api/src/graph.py`):

```
pergunta + histórico(10) + resumo → triagem → rewrite (query autocontida)
    → retrieve híbrido (denso + BM25/RRF) → grade → gerar c/ citação | escalar
```

| Peça | O que faz |
|---|---|
| Triagem | Classifica `infra/sistema/geral` + urgência por regras (sem custo de LLM) |
| Rewrite | Condensa follow-ups (“e o passo 2?”) em busca autocontida com resumo+histórico |
| Retrieve | Embeddings multilíngues + BM25 com stemming PT, fusão RRF por conteúdo, pool largo |
| Grade | Sem trechos → escalação honesta (nunca inventa procedimento) |
| Gerar | LLM (Groq → Ollama Cloud → OpenRouter) com trechos + contexto; fallback extrativo sem chave |
| Memória | Últimas 10 mensagens no prompt + resumo da thread (`threads.resumo`) recompactado a cada 10 msgs |

Chunking v2 (`api/src/chunk.py::chunk_docling`): agrupa blocos do JSON do Docling por
`section_header`, descarta header/footer, preserva tabelas/código inteiros (tabelas
gigantes viram blocos com header repetido — o embedder trunca em 512 tokens),
overlap por sentença e payload `{fonte, pagina, secao, chunk_index, doc_id}`.

## Telas (web `http://localhost:5175`)

Layout fluido (painel até 1760px, responsivo) com sidebar recolhível no desktop
(botão `«/»`: 240px → 64px só ícones, nome da opção em tooltip no hover).

| Tela | Acesso | O que faz |
|---|---|---|
| Chat | todos | Threads estilo ChatGPT (nova/renomear/apagar, título cheio em tooltip, `N msgs · dd/mm/aaaa às hh:mm`); textarea fixa no rodapé (Enter envia, Shift+Enter quebra linha), autoscroll até a última resposta, citações de fonte e badge de escalação |
| Enviar docs | admin | Ingestão Docling por **clique ou arrastar-e-soltar** (dropzone com lista de arquivos, tamanho e remoção) → markdown → chunk → Qdrant |
| Tickets | todos | Últimas interações do próprio usuário |
| Usuários | admin | CRUD de usuários (nome, e-mail, senha, perfil user/admin; bloqueia auto-remoção e auto-rebaixamento) |
| Observabilidade | admin | Log global com filtros (provedor, limite, só escalados) + métricas (total, escaladas e %, usuários ativos, top provedores) |

## Uso rápido

**No Colab (1 clique, recomendado para iniciantes):** abra o botão *Abrir no Colab* acima,
rode as células e aponte para sua API (localhost via túnel ou host). Só precisa de
`requests` — nada de torch/Docling no notebook.

**Local com Docker (completo: web + api + Qdrant):**

```bash
cp .env.example .env   # GROQ_API_KEY (ou Ollama/OpenRouter) + JWT_SECRET
docker compose up -d --build
# web: http://localhost:5175 | api: http://localhost:8002/docs | qdrant: http://localhost:6333/dashboard
```

**Ingestão:** na aba *Enviar docs* (admin) — arraste arquivos ou clique para
selecionar — ou `POST /ingest` — PDF/DOCX/PPTX/XLSX/CSV/
HTML/XML/TXT/MD. Reimportação total via `docker compose exec api python -m src.reingest_v2`.

**Primeiro acesso:** o usuário `fcervan@local` é promovido a `admin` automaticamente
no startup. Entre com ele, gerencie usuários na aba *Usuários* e envie o
`data/raw/manual-smartlabel.pdf` como base inicial.

**API (resumo):** `POST /auth/register|/auth/login`, `GET /me`, `POST /chat|/chat/stream`,
`GET|POST /threads`, `PATCH|DELETE /threads/{id}`, `GET /tickets`,
`GET|POST /users`, `PATCH|DELETE /users/{id}` (admin),
`GET /admin/logs|/admin/stats` (admin). Interativo em `http://localhost:8002/docs`.

## Estrutura

```
assistente-suporte/
├── notebooks/01_assistente_suporte.ipynb  # didático: o grafo isolado, passo a passo
├── notebooks/02_uso_colab.ipynb           # cliente HTTP da API (1 clique no Colab)
├── api/src/
│   ├── main.py            # FastAPI: auth JWT + chat/threads + ingest + tickets + users CRUD + admin logs/stats
│   ├── graph.py           # LangGraph: triagem→rewrite→retrieve→grade→gerar/escalar
│   ├── chunk.py           # chunk_texto/csv + chunk_docling v2 (seção/página/tabela)
│   ├── vector_qdrant.py   # upsert/wipe/busca híbrida (coleção suporte_ti)
│   ├── embeddings.py      # MiniLM multilíngue + BM25 c/ stemming PT + RRF
│   ├── duckdb_store.py    # users (+CRUD), threads (título+resumo), interacoes (+logs/stats globais, ensure_admin)
│   ├── ingest_docling.py  # Docling: raw -> processed (.md + .json)
│   ├── reingest_v2.py     # wipe + reimportação total em v2
│   ├── eval_douradas.py   # eval hit@k sobre tests/douradas.csv
│   ├── llm_client.py      # fallback Groq → Ollama Cloud → OpenRouter
│   └── auth.py            # JWT + hash bcrypt (+guarda admin)
├── web/src/               # React 18 + Vite (Chat c/ textarea+autoscroll, Ingest c/ dropzone, Admin, Usuarios, Observabilidade, Login; sidebar colapsável)
├── tests/                 # 79 testes + CSV dourado (15 perguntas)
└── docker-compose.yml     # api :8002 + web :5175 + qdrant :6333
```

## Qualidade

* **79 testes automatizados** (cobrem API, grafo, chunking, RRF, threads, auth); dependências
  pesadas (Qdrant, HF, Docling) isoladas por stubs/mocks — nenhum teste custa API
* **100% de cobertura** de `api/src` (exigido conceitualmente; `ingest_docling` e vetores
  cobertos via Docling/Qdrant dublados)
* **Eval dourado 15/15** (`hit@4`) sobre a base real ingerida
* Lint + formatação com **Ruff**; pipeline **GitHub Actions** a cada push/PR

```bash
pip install -r requirements-dev.txt
ruff check api/src tests && ruff format --check api/src tests
pytest tests/ -q --cov=api/src --cov-report=term-missing
docker compose exec api python -m src.eval_douradas --csv tests/douradas.csv
```

## Créditos e origem

Projeto derivado do notebook
[agente_de_suporte_langgraph.ipynb](https://github.com/Scoras-Academy/Projetos_Praticos_de_IA/blob/main/Projetos_praticos_de_IA/agente_de_suporte_langgraph.ipynb)
do módulo Projetos Práticos de IA da **Scoras Academy** (prof. **Anderson Amaral**).
A base (grafo triagem → retrieve → gerar com LangGraph) vem de lá; aqui ela foi
evoluída para produto multiusuário: auth JWT, threads com memória e resumo,
ingestão Docling, chunking por estrutura, RAG híbrido com stemming PT, fallback
multi-LLM, frontend React, gestão de usuários, observabilidade, suite de 79 testes e CI.

## Roadmap

* Métrica de latência por resposta na Observabilidade (coluna `duracao_ms` em `interacoes`)
* Título da conversa via LLM (hoje: truncamento da 1ª pergunta)
* Streaming token-a-token real no `/chat/stream` (hoje: simulado por linha)
* Embedding `multilingual-e5` (exige re-embedar a base)
* Postgres se a escrita concorrente estourar o DuckDB embarcado
* Admin da base: listar/apagar documentos por `doc_id`, ver resumos das threads
