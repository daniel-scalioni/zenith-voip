# Diagrama C4 — Componentes (Nível 3)

> Gerado pelo Architect — 2026-06-19
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Propósito

Detalhar os componentes internos dos containers mais relevantes.

## FastAPI Application (Container Principal)

```mermaid
C4Component
  title Diagrama de Componentes — FastAPI Application

  Container_Boundary(api, "FastAPI Application") {
    Component(main, "main.py", "Entry point", "Configura lifespan, health endpoints, CORS")
    Component(auth, "api/auth.py", "JWT Auth Module", "create_access_token, verify_token, require_admin_role")
    Component(ratelimit, "api/rate_limit.py", "Rate Limiter", "100 req/60s por IP (dict in-memory)")
    Component(routers, "api/routers/", "Route Handlers", "CRUD de PBXs (/api/v1/admin/pbxs)")
    Component(ws, "api/websockets.py", "WebSocket Manager", "Agent Assist, SIP auto-link, *88 linkage")
    Component(wh, "api/webhooks.py", "Webhook Dispatcher", "Dispara webhooks pós-chamada")
    Component(esl, "telephony/esl_client.py", "ESL Client", "FreeSWITCH event listener, auto-reconnect")
    Component(audio, "audio/ingestor.py", "Audio Ingestor", "Recebe forked stream WS, publica no Redis")
    Component(telemetry, "observability/telemetry.py", "Telemetry", "OpenTelemetry + Prometheus /metrics")
  }

  ContainerDb(redis, "Redis 7", "Cache + Streams")
  System_Ext(fs, "FreeSWITCH", "ESL + WS")

  Rel(audio, redis, "Publish AudioChunks", "call:events stream")
  Rel(esl, fs, "Listen events", "ESL")
  Rel(ws, redis, "Read/write SIP mappings", "Cache")
  Rel(ws, redis, "Read/write agent sessions", "Cache (TTL 30-120s)")
```

### Componentes da FastAPI

| Componente | Arquivo | Responsabilidade | Confiança |
|-----------|---------|-----------------|-----------|
| **main.py** | `src/main.py` | Entry point FastAPI, lifespan init_db, /health, /ready | 🟢 |
| **Auth Module** | `src/api/auth.py` | Geração JWT, verificação, RBAC (agent/tenant_admin) | 🟢 |
| **Rate Limiter** | `src/api/rate_limit.py` | Rate limit in-memory por IP | 🟢 |
| **PBX Router** | `src/api/routers/pbxs.py` | CRUD de PBXs (admin only) | 🟢 |
| **WebSocket Manager** | `src/api/websockets.py` | Agent assist, SIP auto-link, manual linkage *88, alertas | 🟢 |
| **Webhook Dispatcher** | `src/api/webhooks.py` | Dispara webhooks para URLs configuradas | 🟢 |
| **ESL Client** | `src/telephony/esl_client.py` | Conexão FreeSWITCH ESL, auto-reconnect, SIP mapping | 🟢 |
| **Audio Ingestor** | `src/audio/ingestor.py` | Recebe áudio via WS, detecta canal (🔴 stub), publica evento | 🟢 |
| **Telemetry** | `src/observability/telemetry.py` | OpenTelemetry setup, /metrics Prometheus | 🟢 |

## Worker Application (Container ARQ)

```mermaid
C4Component
  title Diagrama de Componentes — ARQ Worker Container

  Container_Boundary(workers, "ARQ Workers") {
    Component(stt, "stt_autofallback.py", "STT Strategy", "Deepgram → Whisper fallback (500ms/0.3)")
    Component(stt_dg, "stt_deepgram.py", "Deepgram Provider", "Implementa STTStrategy")
    Component(stt_wh, "stt_whisper.py", "Whisper Provider", "Implementa STTStrategy")
    Component(tts, "tts_service.py", "TTS Service", "Piper TTS provider")
    Component(tts_fb, "tts_fallback.py", "TTS Fallback", "WAV local se Piper falhar")
    Component(ext_regex, "extraction/regex_layer.py", "Regex Extractor", "6 padrões: CPF, RG, tel, placa, CEP, cartão")
    Component(ext_llm, "extraction/llm_layer.py", "LLM Extractor", "Correção contextual via Ollama")
    Component(anomaly, "ai/anomaly_detector.py", "Anomaly Detector", "Fury Score + stress patterns")
    Component(consensus, "ai/consensus_graph.py", "Consensus Graph", "LangGraph: extract → review → decide (3 ciclos)")
    Component(pops, "ai/pops_cache.py", "POPs Cache", "Cache Redis de POPs (TTL 1h)")
    Component(persist, "workers/transcript_persist.py", "Transcript Persister", "Buffer + batch insert no PostgreSQL")
    Component(upload, "workers/audio_uploader.py", "Audio Uploader", "Upload para S3")
    Component(cleanup, "workers/audio_cleanup.py", "Audio Cleanup", "Delete S3 lote 1000, cron 03:00")
    Component(postcall, "workers/post_call.py", "Post-Call Worker", "Sentiment (🔴 stub) + audit (🔴 stub)")
  }

  Rel(stt, stt_dg, "Delega", "Strategy")
  Rel(stt, stt_wh, "Fallback", "Strategy")
  Rel(ext_llm, ext_regex, "Corrige", "Dados suspeitos")
  Rel(consensus, ext_regex, "Valida entidades", "Dados extraídos")
  Rel(consensus, anomaly, "Verifica tom", "Score de anomalia")
```

## Fluxo de Componentes por Chamada

```
FreeSWITCH → ESL Client (esl_client.py)
                  ↓
         Audio Ingestor (ingestor.py)
                  ↓
         Redis Stream (call:events)
                  ↓
    ┌──── ARQ Workers ──────────────────────────┐
    │  STT AutoFallback (Deepgram → Whisper)    │
    │  Regex Extraction (CPF, RG, tel, placa…)  │
    │  LLM Correction (Ollama Mistral 7B)       │
    │  Anomaly Detection (Fury Score + Stress)  │
    │  Consensus Graph (3 ciclos LangGraph)     │
    │  Transcript Persist (batch insert)        │
    └────────────────────────────────────────────┘
                  ↓
         WebSocket Manager → Widget Tauri
```
