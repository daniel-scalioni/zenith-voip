# STT, Design

**Interface:** STTStrategy: `transcribe(audio_chunk) → dict`
**Implementações:** DeepgramSTT (primário, nova-2 PT diarizado) → WhisperSTT (fallback)
**AutoFallback:** timeout configurável via STT_FALLBACK_TIMEOUT_MS (default 500ms) → Whisper; confidence <= 0.3 → Whisper
**Origem:** `src/services/stt_autofallback.py:10-20`, `stt_deepgram.py`, `stt_whisper.py` 🟢
