# Módulo: workers

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/workers/audio_cleanup.py` | Limpeza de áudio S3 (cron diário 3h) | 103 |
| `src/workers/audio_uploader.py` | Upload de áudio para S3 | 64 |
| `src/workers/post_call.py` | Workflow pós-chamada (sentiment + audit) | 32 |
| `src/workers/transcript_persist.py` | Persistência em lote de transcrições | 45 |

## Fluxo de Controle

### audio_cleanup.py
- Worker ARQ com cron job (03:00 diário)
- `run_cleanup(ctx)` → lista tenants ativos do DB, executa cleanup por tenant
- `cleanup_tenant_bucket(ctx, tenant_id)` → conecta S3, lista objetos com cutoff de AUDIO_RETENTION_DAYS (90), deleta em lotes de 1000
- Registra métricas: deleted_count, bytes_freed, duration

### audio_uploader.py
- Worker ARQ: `upload_audio_chunk()` e `upload_recording_batch()`
- Para cada chunk: cria bucket se não existir, faz put_object
- Bucket naming: `{prefix}-{tenant_id}`

### post_call.py
- Worker ARQ: `post_call_workflow()` executa sentiment + audit
- Atualmente implementações stub (retornam valores fixos)
- Publica resultado no Redis Stream "call:post"

### transcript_persist.py
- `TranscriptPersister` faz buffer de transcrições no Redis (lista) e flush em lote
- `buffer_transcript()` → rpush no Redis
- `flush_batch()` → lê lista, cria Transcript objects, insere no DB, apaga lista

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Cleanup roda diariamente às 3h | `audio_cleanup.py:101` | 🟢 |
| Retenção de áudio: 90 dias | `audio_cleanup.py:32` | 🟢 |
| Delete em lotes de 1000 objetos S3 | `audio_cleanup.py:51-54` | 🟢 |
| Transcrições bufferizadas no Redis e persistidas em lote | `transcript_persist.py:14-42` | 🟢 |
| Post-call workflow (stub) | `post_call.py:7-13` | 🟡 INFERIDO |
