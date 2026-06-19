# Legacy Impact — AI Audio Hub (001)

> Data: `2026-05-17`
> Feature: `001-ai-audio-hub`
> Tipo: Greenfield (sem legado)

## Observação

Projeto greenfield — todos os componentes são novos. Não há regras de negócio legadas sendo alteradas ou removidas. O impacto documentado abaixo reflete a criação de componentes do zero, classificados para rastreabilidade futura.

## Tabela de Impacto

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|----------------|------------|------|------------|---------------|
| `requirements.txt` | Infraestrutura | componente-novo | LOW | Dependências Python do projeto |
| `docker-compose.yml` | Infraestrutura | componente-novo | CRITICAL | Orquestração de todos os containers |
| `Dockerfile` | Infraestrutura | componente-novo | CRITICAL | Imagem base do backend FastAPI |
| `bootstrap.sh` | Infraestrutura | componente-novo | MEDIUM | Script de setup automatizado |
| `prometheus.yml` | Observabilidade | componente-novo | MEDIUM | Configuração de scraping |
| `src/config.py` | Core | componente-novo | CRITICAL | Configurações centralizadas do sistema |
| `src/main.py` | Core | componente-novo | CRITICAL | Entry point FastAPI |
| `src/database/models.py` | Database | componente-novo | CRITICAL | Modelos ORM (calls, transcripts, insights, stt_metrics) |
| `src/database/database.py` | Database | componente-novo | CRITICAL | Conexão e inicialização do banco |
| `alembic.ini` | Database | componente-novo | MEDIUM | Configuração Alembic |
| `alembic/env.py` | Database | componente-novo | MEDIUM | Ambiente de migrações |
| `alembic/versions/001_initial.py` | Database | componente-novo | CRITICAL | Migração inicial do schema |
| `freeswitch/conf/dialplan/default.xml` | Telefonia | componente-novo | CRITICAL | Proxy transparente SIP + audio fork |
| `freeswitch/conf/sip_profiles/internal.xml` | Telefonia | componente-novo | HIGH | Perfil SIP com TLS/SRTP |
| `freeswitch/conf/autoload_configs/modules.conf.xml` | Telefonia | componente-novo | CRITICAL | Módulos FreeSWITCH (mod_audio_fork, etc) |
| `src/audio/ingestor.py` | Telefonia | componente-novo | CRITICAL | Ingestor de áudio WebSocket com diarização |
| `src/services/base.py` | Core | componente-novo | CRITICAL | Strategy, Repository, Factory patterns |
| `src/services/stt_deepgram.py` | STT | componente-novo | HIGH | STT primário (Deepgram) |
| `src/services/stt_whisper.py` | STT | componente-novo | HIGH | Fallback STT local (Whisper.cpp) |
| `src/services/stt_autofallback.py` | STT | componente-novo | CRITICAL | Auto-fallback primary→fallback |
| `src/services/tts_service.py` | TTS | componente-novo | HIGH | Síntese de voz (Piper TTS) |
| `src/services/tts_fallback.py` | TTS | componente-novo | MEDIUM | Fallback WAV pré-gravados |
| `src/events/redis_streams.py` | Event Bus | componente-novo | CRITICAL | Barramento de eventos Redis Streams |
| `src/extraction/regex_layer.py` | Extração | componente-novo | HIGH | Camada 1 Triage (Regex) |
| `src/extraction/llm_layer.py` | Extração | componente-novo | HIGH | Camada 2 Triage (LLM local) |
| `src/ai/consensus_graph.py` | IA | componente-novo | CRITICAL | Grafo LangGraph multi-agente |
| `src/ai/pops_cache.py` | IA | componente-novo | MEDIUM | Cache de POPs em Redis |
| `src/ai/anomaly_detector.py` | IA | componente-novo | MEDIUM | Detecção de fúria/anomalia |
| `src/telephony/esl_client.py` | Telefonia | componente-novo | CRITICAL | Conexão ESL FreeSWITCH |
| `src/telephony/whisper_mode.py` | Telefonia | componente-novo | HIGH | Whisper mode (uuid_play agent) |
| `src/telephony/filler_audio.py` | Telefonia | componente-novo | MEDIUM | Áudio de espera (uuid_play customer) |
| `src/workers/post_call.py` | Workers | componente-novo | HIGH | Worker Arq pós-chamada |
| `src/workers/transcript_persist.py` | Workers | componente-novo | HIGH | Batch insert de transcripts |
| `src/api/auth.py` | API | componente-novo | HIGH | JWT authentication |
| `src/api/rate_limit.py` | API | componente-novo | MEDIUM | Rate limiting middleware |
| `src/api/websockets.py` | API | componente-novo | CRITICAL | WebSocket Agent Assist |
| `src/api/webhooks.py` | API | componente-novo | HIGH | Webhook dispatcher |
| `src/observability/telemetry.py` | Observabilidade | componente-novo | HIGH | OpenTelemetry + Prometheus |
| `grafana/dashboards/ai-hub.json` | Observabilidade | componente-novo | MEDIUM | Dashboard Grafana |
| `widget/src-tauri/tauri.conf.json` | Widget | componente-novo | MEDIUM | Configuração Tauri |
| `widget/src-tauri/src/main.rs` | Widget | componente-novo | MEDIUM | Lógica nativa Tauri |
| `widget/src/index.html` | Widget | componente-novo | MEDIUM | UI do widget desktop |
| `widget/src/ws-client.js` | Widget | componente-novo | MEDIUM | WebSocket client do widget |
| `tests/test_infra.py` | Testes | componente-novo | MEDIUM | Testes de infraestrutura |
| `tests/test_freeswitch_esl.py` | Testes | componente-novo | MEDIUM | Testes ESL FreeSWITCH |
| `tests/test_bunker_sticky.py` | Testes | componente-novo | MEDIUM | Testes BunkerWeb WAF |
| `tests/test_chaos_restart.py` | Testes | componente-novo | MEDIUM | Teste de caos restart |
| `tests/test_whisper_isolation.py` | Testes | componente-novo | MEDIUM | Teste de isolamento Whisper |

## Preservadas

n/a — Projeto greenfield, sem regras de negócio legadas.

## Modificadas

n/a — Projeto greenfield, sem regras de negócio legadas alteradas.
