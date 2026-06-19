# Workers, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

| Worker | Função | Gatilho |
|--------|--------|---------|
| audio_cleanup | `cleanup_old_audio()` | Cron ARQ 03:00 |
| audio_uploader | `upload_audio(call_id, audio)` | Evento stream |
| post_call | `run_post_call(call_id)` | Evento CHANNEL_HANGUP |
| transcript_persist | `persist_transcripts()` | Batch a cada 5s |

## Fluxo Principal (Cleanup)

1. Cron ARQ dispara `cleanup_old_audio()` às 03:00 — `src/workers/audio_cleanup.py:101`
2. Lista objetos com mais de 90 dias no S3 — `src/workers/audio_cleanup.py:32`
3. Deleta em lotes de até 1000 objetos — `src/workers/audio_cleanup.py:51-54`

## Fluxo Principal (Transcript Persist)

1. Transcripts bufferizados no Redis em lista `transcripts:batch:{call_id}`
2. A cada 5s (BATCH_INSERT_INTERVAL_SECONDS), flush para PostgreSQL
3. Insert em lote para tabela `transcripts`

## Lacunas

- 🔴 `analyze_sentiment()` — retorna stub, não implementado — `src/workers/post_call.py:7-12`
- 🔴 `audit_procedure()` — retorna stub, não implementado — `src/workers/post_call.py:7-12`
- 🟡 Sem monitoramento de workers (dead letters, retry)
