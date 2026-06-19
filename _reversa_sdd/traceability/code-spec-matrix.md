# Code/Spec Matrix — zenith-voip

> Gerado pelo Writer — 2026-06-19

## Legenda

| Cobertura | Significado |
|-----------|-------------|
| 🟢 | Spec completa (requirements + design + tasks) |
| 🟡 | Spec parcial (pelo menos requirements) |
| n/a | Nenhuma spec correspondente |

## Matriz

| Arquivo do Legado | Unit | Cobertura |
|-------------------|------|-----------|
| `src/main.py` | `api/` | 🟢 |
| `src/config.py` | `api/` | 🟢 |
| `src/api/auth.py` | `api/auth/` | 🟢 |
| `src/api/rate_limit.py` | `api/` | 🟢 |
| `src/api/routers/pbxs.py` | `api/pbx-management/` | 🟢 |
| `src/api/websockets.py` | `api/websocket/` | 🟢 |
| `src/api/webhooks.py` | `api/webhooks/` | 🟢 |
| `src/ai/anomaly_detector.py` | `ai/anomaly-detection/` | 🟢 |
| `src/ai/consensus_graph.py` | `ai/consensus-graph/` | 🟢 |
| `src/ai/pops_cache.py` | `ai/` | 🟢 |
| `src/audio/ingestor.py` | `audio/audio-ingestion/` | 🟢 |
| `src/database/database.py` | `database/multitenancy/` | 🟢 |
| `src/database/models.py` | `database/` | 🟢 |
| `src/events/redis_streams.py` | `events/event-bus/` | 🟢 |
| `src/extraction/regex_layer.py` | `extraction/data-extraction/` | 🟢 |
| `src/extraction/llm_layer.py` | `extraction/data-extraction/` | 🟢 |
| `src/observability/telemetry.py` | `observability/telemetry-metrics/` | 🟢 |
| `src/utils/telemetry.py` | `observability/telemetry-metrics/` | 🟢 |
| `src/services/base.py` | `services/` | 🟢 |
| `src/services/stt_autofallback.py` | `services/stt/` | 🟢 |
| `src/services/stt_deepgram.py` | `services/stt/` | 🟢 |
| `src/services/stt_whisper.py` | `services/stt/` | 🟢 |
| `src/services/tts_service.py` | `services/tts/` | 🟢 |
| `src/services/tts_fallback.py` | `services/tts/` | 🟢 |
| `src/telephony/esl_client.py` | `telephony/esl-integration/` | 🟢 |
| `src/telephony/whisper_mode.py` | `telephony/whisper-mode/` | 🟢 |
| `src/telephony/filler_audio.py` | `telephony/filler-audio/` | 🟢 |
| `src/workers/audio_cleanup.py` | `workers/audio-cleanup/` | 🟢 |
| `src/workers/audio_uploader.py` | `workers/audio-upload/` | 🟢 |
| `src/workers/post_call.py` | `workers/post-call/` | 🟢 |
| `src/workers/transcript_persist.py` | `workers/transcript-persist/` | 🟢 |
| `widget/src/index.html` | `widget/desktop-widget/` | 🟢 |
| `widget/src/ws-client.js` | `widget/desktop-widget/` | 🟢 |
| `widget/src-tauri/src/main.rs` | `widget/desktop-widget/` | 🟢 |
| `widget/src-tauri/tauri.conf.json` | `widget/desktop-widget/` | 🟢 |
| `docker-compose.yml` | `infra/deployment/` | 🟢 |
| `docker-compose.app.yml` | `infra/deployment/` | 🟢 |
| `docker-compose.infra.yml` | `infra/deployment/` | 🟢 |
| `Dockerfile` | `infra/deployment/` | 🟢 |
| `deploy.sh` | `infra/deployment/` | 🟢 |
| `prometheus.yml` | `infra/monitoring/` | 🟢 |
| `grafana/dashboards/ai-hub.json` | `infra/monitoring/` | 🟢 |
| `freeswitch/conf/dialplan/default.xml` | `telephony/esl-integration/` | 🟢 |
| `freeswitch/conf/sip_profiles/internal.xml` | `telephony/esl-integration/` | 🟢 |
| `alembic/versions/001_initial.py` | `database/migrations/` | 🟢 |
| `alembic/versions/002_tenants_pbxs.py` | `database/migrations/` | 🟢 |
| `alembic/versions/003_tenant_schema_tables.py` | `database/migrations/` | 🟢 |
| `src/_version.py` | n/a | n/a |
| `bootstrap.sh` | n/a | n/a |
| `bump-version.sh` | n/a | n/a |
| `scripts/` | n/a | n/a |
| `tests/` | n/a | n/a |
| `specs/` | n/a | n/a |

## Resumo

| Métrica | Valor |
|---------|-------|
| Arquivos de código mapeados | 43 |
| Arquivos sem spec (n/a) | 5 |
| Cobertura estimada | ~90% |
