# Ingestão de Áudio, Design

**Interface:** `handle_forked_stream(call_id, websocket) → None`
**Payload:** AudioChunk {call_id, channel, data(bytes), timestamp}
**Fluxo:** handle_forked_stream → **valida `call_id` contra `stream_metadata` (ver Segurança abaixo)** → register metadata → loop receive → de-interleaving tx/rx (validado, feature `007-audio-stream-migration`) → publish Redis
**Origem:** `src/audio/ingestor.py` 🟢

**Segurança (2026-07-12, GAP-22):** `handle_forked_stream` recusa a conexão (`websocket.close(code=4401)`, antes de `accept()`) se `call_id` não estiver em `self.stream_metadata` — ou seja, só aceita streams para chamadas cujo `CHANNEL_ANSWER` real já foi processado pelo `esl_client` (`register_stream_metadata()`). Antes disso, qualquer `call_id` (inclusive inventado) era aceito e bufferizado sem nenhuma verificação de origem.
