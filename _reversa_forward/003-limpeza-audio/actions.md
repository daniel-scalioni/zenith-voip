# Actions: Worker de Limpeza de Gravações

> Identificador: `003-limpeza-audio`
> Data: `2026-05-21`
> Roadmap: `_reversa_forward/003-limpeza-audio/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 4 |
| Paralelizáveis (`[//]`) | 2 |
| Maior cadeia de dependência | 1 |

## Ações

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T001 | Adicionar `AUDIO_RETENTION_DAYS` e variáveis S3 no config.py | - | `[//]` | `src/config.py` | 🟢 | `[X]` |
| [//] T002 | Adicionar métricas Prometheus de cleanup no telemetry.py | - | `[//]` | `src/utils/telemetry.py` | 🟢 | `[X]` |
| T003 | Criar worker ARQ periódico audio_cleanup.py | T001, T002 | - | `src/workers/audio_cleanup.py` | 🟢 | `[X]` |
| T004 | Adicionar serviço worker ARQ no docker-compose.yml | T003 | - | `docker-compose.yml` | 🟢 | `[X]` |

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-05-21 | Versão inicial gerada manualmente | reversa |
