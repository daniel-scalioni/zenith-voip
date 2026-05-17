<!--
Template de corpo do actions.md
Carregado por /reversa-to-do e atualizado por /reversa-coding.
-->

# Actions: AI Audio Hub

> Identificador: `001-ai-audio-hub`
> Data: `2026-05-17`
> Roadmap: `_reversa_forward/001-ai-audio-hub/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 38 |
| Paralelizáveis (`[//]`) | 13 |
| Maior cadeia de dependência | 9 |

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração de infraestrutura local. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T001 | Mapear e instalar libs/agents: LangGraph, Arq, greenswitch (ESL), deepgram-sdk, piper-tts, ollama, spacy, opentelemetry | - | `[//]` | `requirements.txt` | 🟢 | `[X]` |
| [//] T002 | Criar Docker Compose completo: FreeSWITCH, PostgreSQL, Redis, FastAPI x2, BunkerWeb WAF, Ollama, Piper TTS, Prometheus, Grafana, Loki | - | `[//]` | `docker-compose.yml` | 🟢 | `[X]` |
| [//] T003 | Criar `bootstrap.sh` para setup automatizado do ambiente dev (gera configs FS, testa SIP, gera .env) | - | `[//]` | `bootstrap.sh` | 🟢 | `[X]` |
| T004 | Configurar Alembic + migrações + criar tabelas DB (calls, transcripts, call_insights, stt_metrics) | T002 | - | `src/database/models.py` | 🟢 | `[X]` |
| T005 | Provisionar FreeSWITCH como Proxy Transparente SIP e executar PoC de bypass com PBX | T002 | - | `freeswitch/conf/dialplan/default.xml` | 🟢 | `[X]` |
| T006 | Configurar TLS/SRTP no FreeSWITCH + JWT e rate limiting no FastAPI | T002 | - | `freeswitch/conf/sip_profiles/internal.xml` | 🟢 | `[X]` |
| T007 | Criar serviços base: Strategy (interfaces STT/TTS/LLM), Repository (DB), Factory (pipeline por tenant) | T004 | - | `src/services/base.py` | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Testes que precisam existir antes ou logo após o núcleo. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T008 | Validar conexão DB, Redis, Ollama e health dos containers | T002 | `[//]` | `tests/test_infra.py` | 🟢 | `[X]` |
| [//] T009 | Validar resposta e latência do ESL no FreeSWITCH (chamada de teste SIP) | T005 | `[//]` | `tests/test_freeswitch_esl.py` | 🟢 | `[X]` |
| [//] T010 | Validar BunkerWeb WAF com sticky sessions por header X-Call-ID | T002 | `[//]` | `tests/test_bunker_sticky.py` | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Lógica central da feature. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T011 | Habilitar `mod_audio_fork` com envio via WebSocket (ws://backend/audio-stream) no FreeSWITCH | T005 | - | `freeswitch/conf/autoload_configs/modules.conf.xml` | 🟢 | `[X]` |
| T012 | Implementar ingestor de áudio WebSocket no FastAPI com separação de canais TX/RX (Speaker Diarization Camada 1) | T011, T007 | - | `src/audio/ingestor.py` | 🟢 | `[X]` |
| T013 | Implementar `DeepgramSTT` (primário) no Strategy de STT com `diarize:true` | T012 | - | `src/services/stt_deepgram.py` | 🟢 | `[X]` |
| T014 | Implementar `WhisperCppSTT` (fallback local) no Strategy de STT | T012 | - | `src/services/stt_whisper.py` | 🟢 | `[X]` |
| T015 | Implementar `AutoFallbackSTT` que alterna Deepgram→Whisper.cpp se timeout > 500ms | T013, T014 | - | `src/services/stt_autofallback.py` | 🟢 | `[X]` |
| T016 | Configurar Redis Streams (XADD/XREADGROUP/XACK) como Event Bus unificado | T007 | - | `src/events/redis_streams.py` | 🟢 | `[X]` |
| T017 | Implementar Extrator Regex/spaCy (Camada 1 do Triage) para CPF, RG, Placa | T015 | - | `src/extraction/regex_layer.py` | 🟢 | `[X]` |
| T018 | Implementar invocação LLM local (Mistral 7B via Ollama) como Camada 2 do Triage | T017 | - | `src/extraction/llm_layer.py` | 🟢 | `[X]` |
| T019 | Implementar TTS Local (Piper TTS) como microserviço HTTP | T001 | - | `src/services/tts_service.py` | 🟢 | `[X]` |
| T020 | Implementar fallback WAV pré-gravados para TTS + health check `/health` | T019 | - | `src/services/tts_fallback.py` | 🟢 | `[X]` |
| T021 | Criar Grafo LangGraph (Extrator → Revisor → Decisor) com RedisSaver checkpointer | T016, T018 | - | `src/ai/consensus_graph.py` | 🟢 | `[X]` |
| T022 | Implementar cache de POPs (regras de condomínio) em Redis para o grafo | T021 | - | `src/ai/pops_cache.py` | 🟢 | `[X]` |
| T023 | Implementar ESL Client com mapeamento de UUIDs por perna (agent_uuid, customer_uuid) | T011 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T024 | Implementar Whisper Mode: `uuid_play <agent_uuid>` via ESL | T023, T019 | - | `src/telephony/whisper_mode.py` | 🟢 | `[X]` |
| T025 | Implementar Filler Audio: `uuid_play <customer_uuid>` via ESL | T023 | - | `src/telephony/filler_audio.py` | 🟢 | `[X]` |
| [//] T026 | Implementar Worker Arq para processamento pós-chamada (sentimento + auditoria) via Redis Streams | T016 | `[//]` | `src/workers/post_call.py` | 🟢 | `[X]` |
| T027 | Implementar batch insert de transcripts (Redis List → PostgreSQL em lote no fim da chamada) | T026, T004 | - | `src/workers/transcript_persist.py` | 🟢 | `[X]` |

## Fase 4, Integração

<!-- Cola com outras partes do sistema, contratos externos, ganchos. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T028 | Construir WebSocket Server para Agent Assist (Live Transcript + Entidades + Alertas) com JWT | T015, T018 | - | `src/api/websockets.py` | 🟢 | `[X]` |
| T029 | Desenvolver disparador de Webhook Pós-Chamada (payload com sentimento, auditoria, consenso) via Arq | T026 | - | `src/api/webhooks.py` | 🟢 | `[X]` |
| T030 | Inicializar projeto Tauri com Vanilla HTML/CSS/JS (scaffold, always-on-top, system tray) | T001 | - | `widget/src-tauri/tauri.conf.json` | 🟢 | `[X]` |
| T031 | Implementar UI do widget: checklist POP dinâmico + barra de controle (Copiloto/Pausar) + status STT | T030, T028 | - | `widget/src/index.html` | 🟢 | `[X]` |
| T032 | Implementar lógica WebSocket Client no widget (conectar ao FastAPI, receber eventos, atualizar checklist) | T031 | - | `widget/src/ws-client.js` | 🟢 | `[X]` |
| [//] T033 | Implementar auto-show (widget aparece ao detectar chamada) e auto-hide (minimiza ao encerrar) | T032 | `[//]` | `widget/src-tauri/src/main.rs` | 🟢 | `[X]` |

## Fase 5, Polimento

<!-- Logs, telemetria, observabilidade, testes de caos. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T034 | Instrumentar FastAPI com OpenTelemetry (@instrument) + métricas Prometheus | T007 | - | `src/observability/telemetry.py` | 🟢 | `[X]` |
| T035 | Criar dashboard Grafana com métricas STT (p50/p99), taxa de fallback, consenso neg/pos | T034 | - | `grafana/dashboards/ai-hub.json` | 🟢 | `[X]` |
| T036 | Implementar Detecção de Fúria/Anomalia e push de Alerta para Widget via WebSocket | T021, T032 | - | `src/ai/anomaly_detector.py` | 🟢 | `[X]` |
| [//] T037 | Teste de caos: restart container FastAPI durante chamada ativa e verificar recuperação de estado via Redis | T021 | `[//]` | `tests/test_chaos_restart.py` | 🟢 | `[X]` |
| [//] T038 | Teste de isolamento Whisper: gravar ambas as pernas e confirmar que áudio não vaza para perna errada | T024 | `[//]` | `tests/test_whisper_isolation.py` | 🟢 | `[X]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-05-17 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-05-17 | Regenerado após Peer Review de 3 LLMs + Tauri widget. 38 tarefas. | reversa |
