# Upload de Áudio (workers/audio-upload)

**Responsabilidades:** Persistência local da gravação por tenant/call_id (sem S3, decisão de produto em 2026-06-22)
**RF:** Diretório `{RECORDINGS_PATH}/{tenant_id}/{call_id}/{channel}.raw`
**Origem:** `src/workers/audio_uploader.py`
