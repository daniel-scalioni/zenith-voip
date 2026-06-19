# Roadmap: Worker de Limpeza de Gravações

> Identificador: `003-limpeza-audio`
> Data: `2026-05-21`
> Requirements: `_reversa_forward/003-limpeza-audio/requirements.md`

## 1. Resumo

Worker ARQ periódico executado a cada 24h via `arq.cron` que varre buckets MinIO/S3 por tenant e remove objetos de áudio expirados (default 90 dias).

## 2. Delta arquitetural

| Componente | Arquivo | Tipo de mudança | Resumo |
|------------|---------|-----------------|--------|
| Config | `src/config.py` | regra-alterada | Adicionar `AUDIO_RETENTION_DAYS` |
| Telemetria | `src/utils/telemetry.py` | regra-alterada | Adicionar métricas de cleanup |
| Worker | `src/workers/audio_cleanup.py` | componente-novo | Worker periódico de limpeza |
| Infra | `docker-compose.yml` | regra-alterada | Adicionar serviço do worker ARQ |

## 3. Ações

| ID | Descrição | Arquivo alvo |
|----|-----------|-------------|
| T001 | Adicionar `AUDIO_RETENTION_DAYS` no config.py | `src/config.py` |
| T002 | Adicionar métricas Prometheus de cleanup | `src/utils/telemetry.py` |
| T003 | Criar worker ARQ periódico de limpeza | `src/workers/audio_cleanup.py` |
| T004 | Adicionar serviço no docker-compose.yml | `docker-compose.yml` |
