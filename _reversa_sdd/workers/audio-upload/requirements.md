# Upload de Áudio (workers/audio-upload)

**Responsabilidades:** Persistência local da gravação por tenant/call_id (sem S3, decisão de produto em 2026-06-22), em volume RAM (tmpfs, não HD do sistema, desde 2026-07-10) e formato tocável (mp3, não raw, desde 2026-07-10)
**RF:** Diretório `{RECORDINGS_PATH}/{tenant_id}/{call_id}/{channel}.mp3` (mono por canal, PCM16 8kHz→mp3); `.raw` intermediário é apagado após conversão bem-sucedida
**Origem:** `src/workers/audio_uploader.py`
