# Workers — Background Jobs

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Workers ARQ para processamento assíncrono: cleanup de áudio S3, upload, pós-chamada e persistência de transcrições.

## Responsabilidades

- Limpar áudio do S3 com mais de 90 dias (cron diário 03:00)
- Fazer upload de áudio para S3
- Executar workflow pós-chamada (sentimento, auditoria) — 🔴 stubs
- Persistir transcrições em lote no PostgreSQL

## Regras de Negócio

- Cleanup roda diariamente às 03:00 🟢
- Retenção de áudio: 90 dias 🟢
- Delete S3 em lotes de até 1000 objetos 🟢
- Bucket S3 nomeado como {prefix}-{tenant_id} 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Limpar áudio do S3 com mais de 90 dias (cron) | Must |
| RF-02 | Deletar objetos S3 em lotes de 1000 | Must |
| RF-03 | Fazer upload de áudio para S3 | Must |
| RF-04 | Executar análise de sentimento pós-chamada | Should |
| RF-05 | Executar auditoria pós-chamada | Should |
| RF-06 | Persistir transcrições em lote no PostgreSQL | Must |

## Rastreabilidade

| Arquivo | Função | Cobertura |
|---------|--------|-----------|
| `src/workers/audio_cleanup.py` | cleanup cron | 🟢 |
| `src/workers/audio_uploader.py` | S3 upload | 🟢 |
| `src/workers/post_call.py` | `analyze_sentiment()`, `audit_procedure()` | 🟢 (🔴 stubs) |
| `src/workers/transcript_persist.py` | batch persist | 🟢 |
