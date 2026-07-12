# Cleanup de Áudio (workers/audio-cleanup)

**Responsabilidades:** Deletar arquivos locais em `RECORDINGS_PATH` com mtime > `AUDIO_RETENTION_DAYS`, cron a cada 15 min
**Regras:** Retenção padrão de produto = 90 dias (`AUDIO_RETENTION_DAYS` default no código); **MVP Fase 1 (2026-07-10) sobrescreve para ~1h** (`0.0417`, via env do serviço `arq-cleanup`) — gravação é temporária, só para auditoria imediata. Varredura por tenant 🟢
**Origem:** `src/workers/audio_cleanup.py`
