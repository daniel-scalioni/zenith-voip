# Inventário — zenith-voip

> Gerado pelo Reversa Scout em 2026-06-19
> Projeto: **Zenith AI Audio Hub** v1.0.0

## Visão Geral

Sistema de IA para transcrição e análise de chamadas VoIP em tempo real, integrado ao FreeSWITCH. Opera com multitenancy físico (schemas PostgreSQL isolados por tenant), STT com fallback automático (Deepgram → Whisper.cpp), extração de dados por regex + LLM local (Ollama), TTS via Piper, e widget desktop Tauri para operadores.

## Estrutura de Diretórios

```
src/                          # Código-fonte principal (32 arquivos .py)
├── _version.py               # Versão do sistema (1.0.0)
├── config.py                 # Configurações via pydantic-settings
├── main.py                   # Entry point FastAPI
├── api/                      # Camada de API
│   ├── auth.py               # JWT auth + RBAC
│   ├── rate_limit.py         # Rate limiting in-memory
│   ├── webhooks.py           # Webhook dispatcher
│   ├── websockets.py         # WebSocket para agent assist
│   └── routers/
│       └── pbxs.py           # CRUD de PBXs (/api/v1/admin/pbxs)
├── ai/                       # Camada de IA
│   ├── anomaly_detector.py   # Detecção de anomalias de tom
│   ├── consensus_graph.py    # LangGraph consensus (3 ciclos)
│   └── pops_cache.py         # Cache Redis de POPs
├── audio/                    # Áudio
│   └── ingestor.py           # Ingestão de streams de áudio via WS
├── database/                 # Banco de dados
│   ├── database.py           # Engine, sessions, tenant schema mgmt
│   └── models.py             # ORM: Tenant, PBX, Call, Transcript, etc.
├── events/                   # Eventos assíncronos
│   └── redis_streams.py      # Event bus via Redis Streams
├── extraction/               # Extração de dados
│   ├── llm_layer.py          # Correção contextual via Ollama
│   └── regex_layer.py        # Extração por regex (CPF, RG, placa, etc.)
├── observability/            # Observabilidade
│   └── telemetry.py          # OpenTelemetry + Prometheus metrics
├── services/                 # Serviços de IA
│   ├── base.py               # Interfaces Strategy, Repository, Factory
│   ├── stt_autofallback.py   # AutoFallback STT (Deepgram → Whisper)
│   ├── stt_deepgram.py       # Deepgram STT
│   ├── stt_whisper.py        # Whisper.cpp STT
│   ├── tts_service.py        # Piper TTS
│   └── tts_fallback.py       # TTS com fallback para WAV local
├── telephony/                # Telefonia
│   ├── esl_client.py         # Cliente FreeSWITCH ESL
│   ├── filler_audio.py       # Áudio de preenchimento em chamadas
│   └── whisper_mode.py       # Modo Whisper (TTS no canal do agente)
├── utils/
│   └── telemetry.py          # Métricas Prometheus adicionais
└── workers/                  # Workers ARQ (async redis queue)
    ├── audio_cleanup.py      # Limpeza de áudio S3 (cron diário 3h)
    ├── audio_uploader.py     # Upload de áudio para S3
    ├── post_call.py          # Workflow pós-chamada
    └── transcript_persist.py # Persistência em lote de transcrições

widget/                       # Desktop widget (Tauri)
├── src/
│   ├── index.html            # UI do widget
│   └── ws-client.js          # WebSocket client
└── src-tauri/
    ├── src/main.rs           # Aplicação Tauri em Rust
    └── tauri.conf.json       # Configuração Tauri

tests/                        # Testes (7 arquivos)
├── test_bunker_sticky.py
├── test_chaos_restart.py
├── test_freeswitch_esl.py
├── test_infra.py
├── test_multitenancy.py
├── test_telephony_matching.py
└── test_whisper_isolation.py

alembic/                      # Migrations (3 revisões)
├── env.py
├── script.py.mako
└── versions/
    ├── 001_initial.py
    ├── 002_tenants_pbxs.py
    └── 003_tenant_schema_tables.py

freeswitch/conf/              # Config FreeSWITCH
├── autoload_configs/modules.conf.xml
├── dialplan/default.xml
└── sip_profiles/internal.xml

grafana/dashboards/           # Dashboards
└── ai-hub.json

specs/                        # Documentação complementar
└── architecture-guide.md, deploy.md, apresentacao_comercial.html

scripts/                      # Scripts auxiliares
├── bump-version.sh

_Reversa Forward/             # Ciclo forward (features em andamento)
├── 001-ai-audio-hub/         # Feature 1 (completa)
├── 002-escala-eventos/       # Feature 2 (em coding)
└── 003-limpeza-audio/        # Feature 3 (requirements)
```

## Linguagens

| Linguagem | Extensões | Arquivos |
|-----------|-----------|----------|
| Python    | .py       | 32 (src) + 7 (tests) + 4 (alembic) + 2 (scripts) = 45 |
| Rust      | .rs       | 1 (Tauri) |
| JavaScript| .js       | 2 (widget + ws-client) |
| HTML      | .html     | 1 (widget) + 1 (presentation) |
| JSON      | .json     | 7 (config + grafana) |
| XML       | .xml      | 3 (FreeSWITCH) |
| Shell     | .sh       | 3 (bash scripts) |
| YAML      | .yml      | 5 (docker-compose) |
| MD        | .md       | 4 (documentação) |
| INI       | .ini      | 1 (alembic) |

## Módulos Identificados

1. **api** — API REST + WebSocket + Auth (routers, middleware)
2. **ai** — Detecção de anomalias, grafo de consenso, cache POPs
3. **audio** — Ingestão de streams de áudio
4. **database** — ORM, engine, multitenancy
5. **events** — Event bus Redis Streams
6. **extraction** — Extração de dados (regex + LLM)
7. **observability** — Telemetria e métricas
8. **services** — STT, TTS com fallback
9. **telephony** — FreeSWITCH ESL integration
10. **workers** — Background workers ARQ
11. **widget** — Desktop widget Tauri
12. **infra** — Docker, FreeSWITCH, Grafana, Prometheus, Loki

## Integrações Externas

| Integração | Tipo |
|------------|------|
| Deepgram API | STT (cloud) |
| Ollama (Mistral 7B) | LLM local |
| Piper TTS | TTS local |
| FreeSWITCH ESL | Telefonia |
| PostgreSQL | Banco de dados |
| Redis | Cache, streams, filas |
| S3-compatible | Storage |
| OpenTelemetry | Observabilidade |
| Prometheus | Métricas |
| Grafana + Loki | Dashboards e logs |

## Banco de Dados

**PostgreSQL 16** com esquemas:
- `public`: tenants, pbxs (metadados globais)
- `tenant_*` (1 por tenant): calls, transcripts, call_insights, stt_metrics

Migrations via Alembic (3 revisões).

## Testes

- Framework: **pytest** com suporte asyncio
- **7 arquivos** de teste
- Cobertura estimada: ~30% (testes de integração e infra)
