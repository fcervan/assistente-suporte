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

**Sua base de conhecimento vira um atendente que responde em segundos — com fonte, página e sem inventar.**

Manuais, PDFs, planilhas e procedimentos internos costumam ficar espalhados por pastas, anexos e sistemas. Na hora da dúvida, alguém precisa procurar, interpretar e responder — muitas vezes sob pressão e repetindo a mesma explicação pela enésima vez.

O Assistente de Suporte Técnico transforma esse material em uma central de respostas. A equipe envia os documentos da empresa, faz perguntas em português e recebe respostas baseadas no que foi documentado, com a origem indicada. Quando não há informação suficiente, ele não improvisa: avisa e encaminha o caso para uma pessoa.

> **Em 30 segundos:** envie os documentos → pergunte em linguagem natural → confira a resposta e a fonte.

## O problema

- A informação existe, mas ninguém sabe em qual manual, página ou planilha ela está.
- Cada pessoa responde de um jeito, e o conhecimento fica dependente de quem está de plantão.
- Perguntas repetidas consomem o tempo que deveria ser usado em casos complexos.
- Assistentes genéricos às vezes inventam procedimentos — e uma resposta errada pode gerar retrabalho, risco operacional ou insatisfação.

## O que muda no dia a dia

- **Pergunte como você fala.** Nada de decorar palavras-chave ou navegar por dezenas de documentos.
- **Receba a resposta com origem.** A aplicação mostra a fonte e a página usadas, para conferência rápida.
- **Tenha honestidade quando não sabe.** Sem base suficiente, o caso é escalado em vez de respondido com suposições.
- **Continue a conversa.** O assistente lembra do histórico recente e entende perguntas de acompanhamento como “e o passo 2?”.
- **Organize por conversas.** Threads no estilo ChatGPT para criar, continuar, renomear e apagar atendimentos.
- **Cada pessoa no seu lugar.** Perfis `user` e `admin` controlam quem envia documentos e quem administra a operação.
- **Acompanhe o que acontece.** Painel com histórico de interações, taxa de escalação e uso por provedor de IA.

## Como funciona na prática

1. **Envie o material.** Um administrador arrasta PDFs, DOCX, planilhas ou outros documentos para a aba *Enviar docs*. A aplicação lê, organiza e indexa o conteúdo.
2. **Pergunte em português.** No chat, a pessoa escreve a dúvida como faria para um colega: “Como funciona a autenticação?”, “Qual o prazo de devolução?”.
3. **Confira a resposta.** O assistente responde com base nos documentos e indica a fonte. Se não houver base suficiente, sinaliza a escalação para o time humano.

## Para quem é

- **Suporte técnico e TI**, que precisa responder dúvidas sobre sistemas, APIs, infraestrutura e procedimentos.
- **Atendimento e customer success**, que lidam com as mesmas perguntas todos os dias.
- **Onboarding de equipes**, que precisa tornar o conhecimento interno acessível desde o primeiro dia.
- **Empresas com manuais e procedimentos extensos**, onde encontrar a resposta certa já virou um trabalho à parte.

## Comece agora

### Pré-requisitos

- **Docker + Docker Compose** instalados.
- **Uma chave de LLM** (recomendado: Groq). Ollama Cloud e OpenRouter são fallbacks opcionais.
- **Portas livres:** `5175` (web), `8002` (API) e `6333/6334` (Qdrant).
- **Espaço em disco:** a primeira build baixa a imagem do `docling-service` (~7 GB) e as dependências da API (torch/sentence-transformers).
- **Repositórios irmãos:** clone o `assistente-suporte` e o `docling-service` lado a lado (o compose builda `../docling-service`).

> Sem chave de LLM a aplicação ainda sobe e responde em modo extrativo, mas a qualidade das respostas é menor. Para uso real, configure pelo menos uma chave.

### 1. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` e preencha:

```dotenv
GROQ_API_KEY=sua-chave-groq
JWT_SECRET=um-segredo-longo-e-aleatorio
DOCLING_API_KEY=sua-chave-do-docling
DOCLING_API_KEYS={"assistente-suporte":"<sha256-da-chave>"}
```

As demais variáveis já vêm com valores padrão. O arquivo `.env` contém segredos e **não deve ser versionado**.

O par `DOCLING_API_KEY`/`DOCLING_API_KEYS` é gerado no repositório irmão:

```bash
cd ../docling-service
python scripts/gerar_api_key.py
```

- `DOCLING_API_KEY` (texto puro) fica **somente** no `.env` desta API.
- `DOCLING_API_KEYS` (JSON com o hash SHA-256) é o que o serviço Docling usa para autenticar.
- Em produção, guarde ambos em um gerenciador de segredos — nunca no Git.

### 2. Suba a aplicação

```bash
# Docling externo (padrão): suba a API/web/qdrant e use o docling-service já rodando
docker compose up -d --build

# Alternativa: suba tudo junto pelo compose
docker compose --profile docling up -d --build
```

Com o Docling externo, ele precisa estar acessível pela URL configurada em `DOCLING_URL` (por padrão `http://docling:8765` na rede do compose). Para rodar o `docling-service` fora do compose e ainda usar o nome `docling`:

```bash
docker run -d --name docling-service \
  --network assistente-suporte_default --network-alias docling \
  -p 8765:8765 --env-file ../docling-service/.env --restart unless-stopped \
  docling-service:latest
```

Não suba o perfil `docling` enquanto esse container estiver ativo: os dois disputam a porta 8765 e o alias `docling`.

A primeira execução demora porque baixa e monta a imagem do `docling-service` (~7 GB) e as dependências da API. Acompanhe a subida com:

```bash
docker compose ps
docker compose logs -f api
```

### 3. Abra a aplicação

| Serviço | Endereço |
|---|---|
| Interface web | http://localhost:5175 |
| Documentação interativa da API | http://localhost:8002/docs |
| Docling service (conversão isolada) | http://localhost:8765/docs |
| Painel do Qdrant | http://localhost:6333/dashboard |

### 4. Crie o primeiro administrador

Em uma instalação nova ainda não existe usuário. Crie um administrador pela documentação interativa (`POST /auth/register` em http://localhost:8002/docs) ou pelo terminal:

```bash
curl -X POST http://localhost:8002/auth/register \
  -H "Content-Type: application/json" \
  -d '{"nome":"Administrador","email":"admin@empresa.com","senha":"minha-senha-segura","role":"admin"}'
```

Depois, entre na interface web com esse e-mail e senha.

> Se o usuário `fcervan@local` já existir no banco local, ele é promovido a `admin` automaticamente no startup. A promoção não cria a senha: o cadastro precisa ter sido feito antes.

Em produção, restrinja o endpoint de cadastro, use HTTPS e troque o `JWT_SECRET` por um valor longo e aleatório.

### 5. Envie a primeira base de conhecimento

1. Entre como administrador.
2. Abra a aba **Enviar docs**.
3. Arraste os arquivos ou clique para selecionar.

Formatos aceitos: **PDF, DOCX, PPTX, XLSX, CSV, HTML, XML, TXT e MD** — a conversão é feita pelo `docling-service` e volta como JSON estruturado.

Para testar sem material próprio, use `data/raw/manual-acme-ficticio.pdf` — um manual 100% inventado, gerado por script, sem vínculo com nenhuma empresa real. Depois de ingerido, experimente perguntas como “Como funciona a autenticação?” ou “O que é o método CriarPacote?”.

Reimportação total da base:

```bash
docker compose exec api python -m src.reingest_v2
```

### 6. Comandos do dia a dia

```bash
docker compose --profile docling up -d   # subir a stack local completa
docker compose up -d                     # subir só api/web/qdrant (Docling externo)
docker compose stop                      # parar os containers
docker compose down                      # parar e remover containers (dados persistem)
docker compose logs -f api               # acompanhar logs da API
docker compose logs -f docling           # logs do serviço de conversão
docker compose up -d --build web         # rebuild apenas do frontend (~1 min)
```

### Se algo não subir

| Sintoma | O que verificar |
|---|---|
| Porta em uso | Libere `5175`, `8002` ou `6333/6334`, ou ajuste o mapeamento no `docker-compose.yml`. |
| API não responde | Veja `docker compose logs api` e confirme o `.env` (principalmente `JWT_SECRET` e a chave do provedor). |
| Primeira resposta lenta | O startup faz warm-up dos embeddings; as próximas respostas tendem a ser mais rápidas. |
| Respostas sem fonte ou escaladas | Confirme se os documentos foram ingeridos e se aparecem no painel do Qdrant. |
| Ingestão retorna 502 | Verifique `docker compose logs docling` e se `DOCLING_API_KEY` (API) e `DOCLING_API_KEYS` (serviço) formam o par correto. |
| Docling responde 401/503 | A key está ausente/errada ou `DOCLING_API_KEYS` não foi configurado (o serviço falha fechado). |
| Frontend com tela em branco | Rebuild com `docker compose up -d --build web` e confira a URL da API no console. |

### Atalho para testar sem instalar

O notebook [02_uso_colab.ipynb](notebooks/02_uso_colab.ipynb) funciona como cliente HTTP da API no Google Colab. Ele precisa apontar para uma API acessível (localhost via túnel ou host público) e usa apenas `requests` — sem torch ou Docling no notebook.

## Demonstração

Para provar que a resposta não é só “conversa bonita”, o projeto inclui um **eval dourado** com 16 perguntas sobre o Manual da API Acme Fictícia (`tests/douradas.csv`). O resultado atual é **hit@4 em 16/16**: a resposta correta aparece entre os quatro trechos recuperados em todas as perguntas.

| # | Pergunta | Resultado |
|---|---|---|
| 1 | Como funciona a autenticação? | ✅ seção Autenticação (chave TKF) |
| 2 | O que é o método CriarPacote? | ✅ seções 3, 4 e Anexo B |
| 3 | O que é o campo codigoCliente? | ✅ tabela da seção 4 |
| 4–7 | Responses 200 / 206 / 400 / 401 | ✅ exemplos, seção 5 |
| 8 | Como imprimir as etiquetas? | ✅ Modelo de etiqueta, seção 6 |
| 9 | Disponibilidade da API? | ✅ 24h/7d, seção 1.2 |
| 10 | Posso enviar pedidos um a um? | ✅ “proibido”, seção 1.3 |
| 11–15 | Testes, falhas, acesso, exemplo, conceito | ✅ |
| 16 | Posso enviar mais de um pedido por solicitação? | ✅ “um ou mais pacotes (remessas)”, seção 3 |

A base de demonstração é fictícia e serve apenas para exercitar o pipeline de ingestão, busca e resposta.

> 📸 Prints do chat e da sidebar de conversas entram aqui em breve (`docs/demo-chat.png`, `docs/demo-threads.png`).

## Como funciona por dentro

### Visão geral

```
Ingestão:  upload (admin) → docling-service (HTTP) → markdown/JSON → chunk → embeddings → Qdrant
Chat:      pergunta + histórico + resumo → triagem → rewrite → retrieve híbrido
           → grade → gerar com citação | escalar → log no DuckDB
```

**Stack:** FastAPI + React 18 + LangGraph + Qdrant + DuckDB embarcado + `docling-service` (Docling isolado) + sentence-transformers + BM25 + Docker.

### O grafo LangGraph

`api/src/graph.py`:

```
pergunta + histórico(10) + resumo → triagem → rewrite (query autocontida)
    → retrieve híbrido (denso + BM25/RRF) → grade → gerar c/ citação | escalar
```

| Peça | O que faz |
|---|---|
| Triagem | Classifica `infra/sistema/geral` + urgência por regras, sem custo de LLM. |
| Rewrite | Condensa follow-ups (“e o passo 2?”) em uma busca autocontida usando resumo + histórico. |
| Retrieve | Embeddings multilíngues + BM25 com stemming PT, fusão RRF por conteúdo e pool largo de candidatos. |
| Grade | Sem trechos relevantes → escalação honesta; nunca inventa procedimento. |
| Gerar | LLM (Groq → Ollama Cloud → OpenRouter) com trechos + contexto; fallback extrativo sem chave. |
| Memória | Últimas 10 mensagens no prompt + resumo da thread (`threads.resumo`), recompactado a cada 10 mensagens. |

### Chunking por estrutura

`api/src/chunk.py::chunk_docling` agrupa blocos do JSON do Docling por `section_header`, descarta header/footer, preserva tabelas e código inteiros (tabelas gigantes viram blocos com header repetido; o embedder trunca em 512 tokens), aplica overlap por sentença e grava o payload `{fonte, pagina, secao, chunk_index, doc_id}`.

### Busca híbrida

A recuperação combina dois sinais:

- **Busca densa:** embeddings multilíngues capturam semântica e paráfrases.
- **Busca lexical:** BM25 com stemming em português captura termos exatos, nomes de campos e códigos.
- **Fusão RRF:** os rankings são combinados por conteúdo, reduzindo a dependência de um único método.

### LLMs com fallback

`api/src/llm_client.py` tenta, nesta ordem:

1. **Groq** (`GROQ_API_KEY`, `GROQ_MODEL`)
2. **Ollama Cloud** (`OLLAMA_CLOUD_API_KEY`, `OLLAMA_CLOUD_MODEL`)
3. **OpenRouter** (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`)

Sem nenhuma chave, a resposta é montada de forma extrativa a partir dos trechos recuperados.

## Telas

Interface em http://localhost:5175. O layout é fluido (painel até 1760px) e a sidebar pode ser recolhida no desktop (240px → 64px, com tooltips).

| Tela | Acesso | O que faz |
|---|---|---|
| Chat | todos | Threads estilo ChatGPT (criar, renomear, apagar; título completo em tooltip; `N msgs · dd/mm/aaaa às hh:mm`); textarea fixa no rodapé (Enter envia, Shift+Enter quebra linha), autoscroll, citações de fonte e badge de escalação. |
| Enviar docs | admin | Ingestão pelo `docling-service` por clique ou arrastar-e-soltar (dropzone com lista, tamanho e remoção) → markdown/JSON → chunk → Qdrant. |
| Tickets | todos | Últimas interações do próprio usuário. |
| Usuários | admin | CRUD de usuários (nome, e-mail, senha, perfil `user`/`admin`; bloqueia auto-remoção e auto-rebaixamento). |
| Observabilidade | admin | Log global com filtros (provedor, limite, somente escalados) + métricas (total, escaladas e %, usuários ativos, top provedores). |

## API

Documentação interativa: http://localhost:8002/docs

- `GET /health`
- `POST /auth/register` — `{nome, email, senha, role}` → `{access_token}`
- `POST /auth/login` → `{access_token}`
- `GET /me` — perfil autenticado
- `POST /chat` — `{mensagem, thread_id}` → `{resposta, fontes[{fonte, pagina, score}], escalado, provedor}`
- `POST /chat/stream` — SSE
- `POST /ingest` — upload multipart (admin)
- `GET /tickets` — últimas interações do usuário
- `GET|POST /threads`, `GET /threads/{id}`, `PATCH|DELETE /threads/{id}` — threads e mensagens do usuário
- `GET|POST /users`, `PATCH|DELETE /users/{id}` — CRUD de usuários (admin)
- `GET /admin/logs`, `GET /admin/stats` — observabilidade global (admin)

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
│   ├── embeddings.py      # MiniLM multilíngue + BM25 com stemming PT + RRF
│   ├── duckdb_store.py    # users (+CRUD), threads (título+resumo), interacoes (+logs/stats globais, ensure_admin)
│   ├── ingest_docling.py  # cliente HTTP do docling-service: raw -> processed (.md + .json)
│   ├── reingest_v2.py     # wipe + reimportação total em v2
│   ├── eval_douradas.py   # eval hit@k sobre tests/douradas.csv
│   ├── llm_client.py      # fallback Groq → Ollama Cloud → OpenRouter
│   └── auth.py            # JWT + hash bcrypt (+guarda admin)
├── web/src/               # React 18 + Vite (Chat, Ingest, Admin, Usuarios, Observabilidade, Login; sidebar colapsável)
├── data/                  # raw (originais), processed (.md/.json) e DuckDB
├── tests/                 # 80 testes + CSV dourado (16 perguntas)
└── docker-compose.yml     # api :8002 + web :5175 + qdrant :6333 + docling :8765
```

O Docling vive no repositório irmão **`projetos/docling-service`** (FastAPI + API key + deploy independente). Esta API só conhece o contrato HTTP `/v1/convert`.

## Qualidade

- **86 testes automatizados** cobrindo API, grafo, chunking, RRF, threads, auth, CRUD admin e blindagem anti-marca. Dependências pesadas (Qdrant, HF, HTTP/Docling) são isoladas por stubs/mocks; nenhum teste consome API externa.
- **100% de cobertura** de `api/src`; `ingest_docling` (cliente HTTP) e vetores são cobertos via httpx/Qdrant dublados.
- **Eval dourado 16/16** (`hit@4`) sobre a base fictícia ingerida.
- **Ruff** para lint e formatação, com pipeline de **GitHub Actions** a cada push/PR.

```bash
pip install -r requirements-dev.txt
ruff check api/src tests && ruff format --check api/src tests
pytest tests/ -q --cov=api/src --cov-report=term-missing
docker compose exec api python -m src.eval_douradas --csv tests/douradas.csv
```

## Roadmap

- Métrica de latência por resposta na Observabilidade (coluna `duracao_ms` em `interacoes`)
- Título da conversa via LLM (hoje: truncamento da 1ª pergunta)
- Streaming token-a-token real no `/chat/stream` (hoje: simulado por linha)
- Embedding `multilingual-e5` (exige re-embedar a base)
- Postgres se a escrita concorrente estourar o DuckDB embarcado
- Admin da base: listar/apagar documentos por `doc_id`, ver resumos das threads

## Créditos e origem

Projeto derivado do notebook [agente_de_suporte_langgraph.ipynb](https://github.com/Scoras-Academy/Projetos_Praticos_de_IA/blob/main/Projetos_praticos_de_IA/agente_de_suporte_langgraph.ipynb) do módulo Projetos Práticos de IA da **Scoras Academy** (prof. **Anderson Amaral**).

A base (grafo triagem → retrieve → gerar com LangGraph) vem de lá; aqui ela foi evoluída para produto multiusuário: auth JWT, threads com memória e resumo, ingestão via `docling-service`, chunking por estrutura, RAG híbrido com stemming PT, fallback multi-LLM, frontend React, gestão de usuários, observabilidade, suite de 86 testes e CI. O serviço Docling foi extraído para reutilização por outras aplicações.

Distribuído sob a licença MIT — veja [LICENSE](LICENSE).
