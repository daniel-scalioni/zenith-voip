# Cleanup de Áudio (workers/audio-cleanup)

**Responsabilidades:** Deletar arquivos locais em `RECORDINGS_PATH` com mtime > 90 dias, cron 03:00
**Regras:** Retenção 90 dias; varredura por tenant 🟢
**Origem:** `src/workers/audio_cleanup.py`
