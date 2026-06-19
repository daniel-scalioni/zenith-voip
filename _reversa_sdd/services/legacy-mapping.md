# Módulo: services

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/services/base.py` | Interfaces: Strategy, Repository, Factory | 80 |
| `src/services/stt_autofallback.py` | AutoFallback STT (Deepgram → Whisper) | 28 |
| `src/services/stt_deepgram.py` | Deepgram STT (cloud) | 44 |
| `src/services/stt_whisper.py` | Whisper.cpp STT (local) | 40 |
| `src/services/tts_service.py` | Piper TTS (local) | 26 |
| `src/services/tts_fallback.py` | TTS com fallback WAV local | 27 |

## Fluxo de Controle

### base.py — Padrões
- `Strategy` (ABC): interface execute()
- `STTStrategy` (ABC): transcribe()
- `TTSStrategy` (ABC): synthesize()
- `LLMStrategy` (ABC): analyze()
- `Repository[ModelType]`: CRUD genérico com SQLAlchemy AsyncSession
- `Factory` (ABC): create_pipeline(tenant_id)

### stt_autofallback.py — Algoritmo de Fallback
1. Tenta DeepgramSTT com timeout (500ms configurável)
2. Se timeout ou erro ou confidence <= 0.3 → fallback para WhisperCppSTT
3. Marca fallback_activated no resultado

### stt_deepgram.py
- Usa Deepgram SDK com model nova-2, language pt, diarize, punctuate
- Retorna: text, confidence, words (com word, start, end, speaker)

### stt_whisper.py
- Executa whisper-cpp via subprocess com arquivo temporário
- Retorna: text, confidence (avg_logprob), segments

### tts_service.py
- PiperTTS via HTTP: /synthesize com text, voice, speaker_id
- /health check

### tts_fallback.py
- TTSWithFallback: tenta PiperTTS, se falhar → carrega WAV local do disco

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Fallback STT se timeout > 500ms | `stt_autofallback.py:14-15` | 🟢 |
| Fallback STT se confidence <= 0.3 | `stt_autofallback.py:20` | 🟢 |
| Deepgram model: nova-2, pt-BR | `stt_deepgram.py:15-19` | 🟢 |
| Whisper local via subprocess | `stt_whisper.py:22-36` | 🟢 |
| TTS fallback para WAV local se Piper falhar | `tts_fallback.py:13-17` | 🟢 |
