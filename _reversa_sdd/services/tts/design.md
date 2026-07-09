# TTS, Design

**Interface:** TTSStrategy: `synthesize(text, voice, speaker_id) → bytes`
**Implementações:** PiperTTS (primário), WavFallback (local)
**Origem:** `src/services/tts_service.py`, `src/services/tts_fallback.py` 🟢

**Execução (feature `008-piper-tts-standalone`, 2026-07-09):** `PiperTTS` roda como processo local — API Python do pacote `piper-tts==1.4.2` (`PiperVoice.load()`/`synthesize_wav()`, projeto `OHF-Voice/piper1-gpl`), chamada via `asyncio.to_thread()` para não bloquear o event loop. Não há mais microserviço HTTP separado (o serviço Docker `piper-tts` — imagem `rhasspy/piper-tts:2023.11.14` — nunca existiu, GAP-18). Modelo de voz `pt_BR-faber-medium` vendorizado em `audio/voices/` (gitignored, ~63MB).
