# TTS, Design

**Interface:** TTSStrategy: `synthesize(text, voice, speaker_id) → bytes`
**Implementações:** PiperTTS (primário), WavFallback (local)
**Origem:** `src/services/tts_service.py:10-15`, `src/services/tts_fallback.py:13-17` 🟢
