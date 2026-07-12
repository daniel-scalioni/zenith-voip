# Cleanup de Áudio, Design

**Interface:** `cleanup_tenant_bucket(ctx, tenant_id) → dict` (cron ARQ a cada 15 min — `minute={0,15,30,45}` — via `run_cleanup`; antes era 1x/dia às 03:00, mudou em 2026-07-10 pra respeitar retenção sub-diária)
**Algoritmo:** `os.walk` em `{RECORDINGS_PATH}/{tenant_id}/` → deleta arquivos com `mtime` mais antigo que `AUDIO_RETENTION_DAYS` (substituiu paginação/delete em lote S3 em 2026-06-22). `AUDIO_RETENTION_DAYS` é `float` (não `int`) desde 2026-07-10 — permite retenção sub-diária (ex: `0.0417` ≈ 1h, valor efetivo do MVP Fase 1). É global (todos os tenants), não por-tenant.
**Origem:** `src/workers/audio_cleanup.py` 🟢

**Nota (2026-07-10):** este worker nunca tinha rodado com sucesso como container antes do MVP Fase 1 — dois bugs reais impediam o boot (ver GAP-20 em `gaps.md`): `cron(..., run_on_startup=...)` usava kwarg inexistente (correto é `run_at_startup`), e `WorkerSettings.redis_settings` recebia a DSN do Redis como string crua em vez de `RedisSettings.from_dsn(...)`.
