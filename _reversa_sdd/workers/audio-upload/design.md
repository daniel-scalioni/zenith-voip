# Upload de Áudio, Design

**Interface:** `upload_audio_chunk(ctx, tenant_id, call_id, channel, audio_data) → dict`
**Storage:** volume `recordings_tmpfs` (RAM, `driver_opts: type=tmpfs, size=512m`), montado como `RECORDINGS_PATH=/data/recordings` — substituiu S3 em 2026-06-22 (decisão de produto), e o bind mount em disco (`./data/recordings`) por tmpfs em 2026-07-10 (MVP Fase 1 — gravação não deve ocupar o HD do sistema, combina com retenção curta)
**Path final:** `{RECORDINGS_PATH}/{tenant_id}/{call_id}/{channel}.mp3` (PCM16 8kHz mono → `libmp3lame` via `ffmpeg` subprocess, um arquivo mono por canal — `tx.mp3`/`rx.mp3`, não misturados nem estéreo)
**Fluxo:** grava `{channel}.raw` → converte para `.mp3` via `ffmpeg` → apaga o `.raw` só se a conversão for bem-sucedida. Se `ffmpeg` falhar, mantém o `.raw` e retorna `status: "uploaded_raw_only"` (áudio nunca é perdido, só fica sem conversão)
**Worker:** processado pelo serviço `arq-uploader` (`docker-compose.app.yml`) — antes não existia nenhum container consumindo esse job (ver GAP-12/GAP-14 em `gaps.md`)
**Origem:** `src/workers/audio_uploader.py` 🟢 (conversão mp3 e volume tmpfs adicionados 2026-07-10)
