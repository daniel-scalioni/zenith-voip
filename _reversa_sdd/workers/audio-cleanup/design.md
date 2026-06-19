# Cleanup de Áudio, Design

**Interface:** `cleanup_old_audio() → None` (cron ARQ 03:00)
**Algoritmo:** List objects > 90 days → delete batch (1000) → repeat
**Origem:** `src/workers/audio_cleanup.py:32-101` 🟢
