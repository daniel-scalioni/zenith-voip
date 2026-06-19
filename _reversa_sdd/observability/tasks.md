# Observability, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar setup OpenTelemetry para FastAPI
  - Origem: `src/observability/telemetry.py:15-25`
  - Critério: tracing ativo para requisições HTTP
  - Confiança: 🟢

- [ ] T-02, Implementar 16 métricas Prometheus
  - Origem: `src/utils/telemetry.py`
  - Critério: métricas de STT, LLM, calls, S3, Redis, DB exportadas
  - Confiança: 🟢

- [ ] T-03, Implementar endpoint /metrics
  - Origem: `src/observability/telemetry.py:58-60`
  - Critério: Prometheus consegue scrape do endpoint
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar métricas de STT
- [ ] TT-02, Testar endpoint /metrics
- [ ] TT-03, Testar tracing de requisição HTTP
