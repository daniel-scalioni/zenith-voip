# Dependências — zenith-voip

> **Re-extração incremental — 2026-07-27**: 5 dependências removidas (marcadas com ❌).
> Total: 31 → 26 pacotes Python.

> Gerado pelo Reversa Scout em 2026-06-19

## Gerenciador de Pacotes

**pip** (Python 3.12+) com `requirements.txt`

## Dependências Core

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| fastapi | 0.115.6 | Web framework |
| uvicorn | 0.34.0 | ASGI server |
| pydantic | 2.10.3 | Validação |
| pydantic-settings | 2.7.0 | Config |

## Async / Workers

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| arq | 0.26.1 | Redis task queue |
| httpx | 0.28.1 | HTTP client |
| websockets | 14.1 | WebSocket |

## AI / LangGraph

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| langgraph | 0.2.60 | State graph |
| ~~langgraph-checkpoint-redis~~ | ❌ **removida** 2026-07-09 | Conflito `redis>=6.2` vs `arq` (`redis<6`) — ver ADR-008 |
| langchain-ollama | 0.2.2 | Ollama integration |
| langchain-community | 0.3.14 | LangChain community |

## STT

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| deepgram-sdk | 3.7.0 | Deepgram STT |

## TTS

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| piper-tts | 1.4.2 | Piper TTS **in-process** (API Python, não HTTP) |

## Telefonia

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| ~~greenswitch~~ | ❌ **removida** | Nunca foi usada: o ESL é falado em socket TCP bruto com asyncio |

## Database

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| sqlalchemy | 2.0.36 | ORM |
| asyncpg | 0.30.0 | PostgreSQL async driver |
| alembic | 1.14.0 | Migrations |
| psycopg2-binary | 2.9.10 | PostgreSQL sync driver |

## Redis

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| redis[hiredis] | 5.2.1 | Redis client |
| ~~redis-streams~~ | ❌ **removida** | Streams usados direto pelo cliente `redis` oficial |

## NLP / Extração

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| spacy | 3.8.3 | NLP |
| ~~python-brasilcpf~~ | ❌ **removida** | ⚠️ validar se a extração de CPF perdeu validação de dígito verificador |

## Observabilidade

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| opentelemetry-api | 1.29.0 | OpenTelemetry |
| opentelemetry-sdk | 1.29.0 | OpenTelemetry SDK |
| opentelemetry-instrumentation-fastapi | 0.50b0 | FastAPI instrumentation |
| opentelemetry-exporter-otlp | 1.29.0 | OTLP exporter |
| prometheus-client | 0.21.1 | Prometheus metrics |

## Storage

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| ~~boto3~~ | ❌ **removida** 2026-07-10 | S3 saiu do projeto — gravação em tmpfs local (ADR-009) |

## Utilitários

| Dependência | Versão | Categoria |
|-------------|--------|-----------|
| python-multipart | 0.0.19 | Multipart parsing |
| python-jose[cryptography] | 3.3.0 | JWT |
| pyjwt | 2.10.1 | JWT |
| tenacity | 9.0.0 | Retry |
| orjson | 3.10.12 | Fast JSON |

## Infraestrutura (Docker)

| Serviço | Imagem | Versão |
|---------|--------|--------|
| PostgreSQL | postgres | 16-alpine |
| Redis | redis | 7-alpine |
| Prometheus | prom/prometheus | v2.55.1 |
| Grafana | grafana/grafana | 11.3.0 |
| Loki | grafana/loki | 3.2.1 |
| FreeSWITCH | safarov/freeswitch | 1.10.12 |
| Ollama | ollama/ollama | 0.5.7 |
| ~~Piper TTS~~ | ❌ container removido — TTS roda dentro da FastAPI | — |
| BunkerWeb | bunkerity/bunkerweb | 1.5.12 |

## Desktop Widget

- **Tauri** (Rust) — versão conforme Cargo.toml do widget
