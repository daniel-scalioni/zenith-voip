# Upload de Áudio, Design

**Interface:** `upload_audio_chunk(ctx, tenant_id, call_id, channel, audio_data) → dict`
**Storage:** disco local, montado no mesmo host Docker do FreeSWITCH (`RECORDINGS_PATH`, padrão `/data/recordings`) — substituiu S3 em 2026-06-22, decisão de produto
**Path:** `{RECORDINGS_PATH}/{tenant_id}/{call_id}/{channel}.raw`
**Worker:** processado pelo serviço `arq-uploader` (`docker-compose.app.yml`) — antes não existia nenhum container consumindo esse job (ver GAP-12/GAP-14 em `gaps.md`)
**Origem:** `src/workers/audio_uploader.py` 🟢
