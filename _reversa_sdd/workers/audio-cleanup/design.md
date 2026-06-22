# Cleanup de Áudio, Design

**Interface:** `cleanup_tenant_bucket(ctx, tenant_id) → dict` (cron ARQ 03:00, via `run_cleanup`)
**Algoritmo:** `os.walk` em `{RECORDINGS_PATH}/{tenant_id}/` → deleta arquivos com `mtime` mais antigo que `AUDIO_RETENTION_DAYS` (substituiu paginação/delete em lote S3 em 2026-06-22)
**Origem:** `src/workers/audio_cleanup.py` 🟢
