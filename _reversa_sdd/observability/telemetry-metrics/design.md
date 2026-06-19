# Telemetria e Métricas, Design

**Interface:** `setup_telemetry(app) → None`, `/metrics` endpoint
**Métricas:** 16 métricas (STT, LLM, calls, S3, Redis, DB) via prometheus-client
**Tracing:** OpenTelemetry com exportador OTLP
**Origem:** `src/observability/telemetry.py:15-60`, `src/utils/telemetry.py` 🟢
