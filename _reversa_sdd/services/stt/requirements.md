# STT — Speech-to-Text (services/stt)

**Responsabilidades:** Transcrição com fallback automático (Deepgram → Whisper)
**Regras:** Timeout 500ms, confidence <= 0.3 aciona fallback 🟢
**Origem:** `src/services/stt_autofallback.py`, `stt_deepgram.py`, `stt_whisper.py`
