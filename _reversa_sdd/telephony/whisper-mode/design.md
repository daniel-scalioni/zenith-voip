# Whisper Mode, Design

**Interface:** `whisper_to_agent(call_id, text) → dict`
**Fluxo:** Recebe texto → chama TTS → envia áudio para canal do agente via ESL
**Dependências:** services/tts (Piper TTS)
**Origem:** `src/telephony/whisper_mode.py:15-30` 🟢
