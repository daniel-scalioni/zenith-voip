# Módulo: observability

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/observability/telemetry.py` | OpenTelemetry + Prometheus metrics | 84 |
| `src/utils/telemetry.py` | Métricas Prometheus adicionais | 108 |

## Fluxo de Controle

### observability/telemetry.py
- `setup_telemetry(app)` → inicializa TracerProvider, instrumenta FastAPI, expõe /metrics
- Métricas: stt_latency, stt_fallback_total, llm_inference_latency, calls_active, call_duration, consensus_decisions

### utils/telemetry.py
- Métricas operacionais: tenant_schemas_active, redis_stream_events, sip_mappings, websocket_connections, db_pool_connections, multi_schema_query_duration
- Métricas de cleanup: audio_cleanup_files_deleted, bytes_freed, duration, errors

## Métricas Prometheus

| Métrica | Tipo | Labels |
|---------|------|--------|
| stt_latency_ms | Histogram | provider |
| stt_fallback_total | Counter | from_provider, to_provider |
| llm_inference_latency_ms | Histogram | model |
| calls_active | Gauge | - |
| call_duration_seconds | Histogram | - |
| consensus_decisions_total | Counter | decision |
| tenant_schemas_active | Gauge | - |
| redis_stream_events_total | Counter | stream, tenant_id |
| sip_mappings_active | Gauge | - |
| websocket_connections_active | Gauge | tenant_id |
| db_pool_connections | Gauge | - |
| multi_schema_query_duration_seconds | Histogram | schema |
| audio_cleanup_files_deleted_total | Counter | tenant_id |
| audio_cleanup_bytes_freed_total | Counter | tenant_id |
| audio_cleanup_duration_seconds | Histogram | - |
| audio_cleanup_errors_total | Counter | tenant_id |
