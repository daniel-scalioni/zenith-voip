# Upload, Tarefas

- [x] T-01: Implementar persistência local da gravação (substituiu S3 em 2026-06-22) 🟢
  - `upload_audio_chunk`/`upload_recording_batch` já existiam mas nunca eram chamados (gap não documentado, ver GAP-12 em `gaps.md`); agora enfileirados via `enqueue_recording_upload` no hangup (`src/telephony/esl_client.py`) e processados pelo serviço `arq-uploader` (ver GAP-14)
  - Path: `{RECORDINGS_PATH}/{tenant_id}/{call_id}/{channel}.raw`
  - Testes: `tests/test_audio_uploader.py` (verde, escreve em `tmp_path`)
