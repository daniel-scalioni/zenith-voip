# Observability — Observabilidade

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Telemetria, métricas e tracing do sistema via OpenTelemetry + Prometheus.

## Responsabilidades

- Instrumentar FastAPI com OpenTelemetry
- Exportar 16 métricas Prometheus (STT, LLM, chamadas, S3, Redis, DB)
- Expor endpoint `/metrics`

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Instrumentar FastAPI com OpenTelemetry | Must |
| RF-02 | Exportar métricas de STT (latência, taxa de fallback) | Must |
| RF-03 | Exportar métricas de chamadas (total, duração, status) | Must |
| RF-04 | Exportar métricas de LLM (latência, tokens) | Should |
| RF-05 | Exportar métricas de S3 (upload, download) | Should |
| RF-06 | Exportar métricas de Redis e DB | Should |
| RF-07 | Expor endpoint `/metrics` para Prometheus | Must |

## Rastreabilidade

| Arquivo | Função | Cobertura |
|---------|--------|-----------|
| `src/observability/telemetry.py` | OpenTelemetry setup | 🟢 |
| `src/utils/telemetry.py` | Métricas Prometheus | 🟢 |
