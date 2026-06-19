# Ingestão de Áudio, Design

**Interface:** `handle_forked_stream(call_id, websocket) → None`
**Payload:** AudioChunk {call_id, channel, data(bytes), timestamp}
**Fluxo:** handle_forked_stream → register metadata → loop receive → _detect_channel (🔴 tx hardcoded) → publish Redis
**Origem:** `src/audio/ingestor.py:30-71` 🟢
