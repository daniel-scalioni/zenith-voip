# Observability, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

| Símbolo | Assinatura | Retorno |
|---------|-----------|---------|
| `setup_telemetry` | `(app: FastAPI)` | `None` |
| `increment_metric` | `(name: str, labels: dict)` | `None` |
| `observe_latency` | `(name: str, value: float, labels: dict)` | `None` |

### Métricas Prometheus (16)

| Categoria | Métricas |
|-----------|----------|
| STT | stt_requests_total, stt_latency_ms, stt_fallback_total, stt_errors_total |
| LLM | llm_requests_total, llm_latency_ms, llm_tokens_total |
| Chamadas | calls_total, calls_duration_seconds, calls_status_total |
| S3 | s3_upload_total, s3_download_total, s3_errors_total |
| Redis | redis_operations_total, redis_latency_ms |
| DB | db_queries_total, db_latency_ms |

## Fluxo Principal

1. `setup_telemetry(app)` no lifespan da FastAPI — `src/observability/telemetry.py:15-25`
2. OpenTelemetry instrumenta requisições HTTP automaticamente
3. Métricas incrementadas manualmente nos pontos relevantes do código
4. `/metrics` exposto para scrape do Prometheus — `src/observability/telemetry.py:58-60`

## Riscos e Lacunas

- 🟡 Sem tracing distribuído entre API e Workers (apenas instrumentação HTTP)
- 🟡 Sem alertas configurados no Prometheus/Grafana
