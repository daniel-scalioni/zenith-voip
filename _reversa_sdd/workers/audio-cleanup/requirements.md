# Cleanup de Áudio (workers/audio-cleanup)

**Responsabilidades:** Deletar áudio S3 com > 90 dias, cron 03:00, lotes de 1000
**Regras:** Retenção 90 dias; delete em lotes de 1000 🟢
**Origem:** `src/workers/audio_cleanup.py`
