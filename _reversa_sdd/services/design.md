# Services, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

| Símbolo | Assinatura | Retorno |
|---------|-----------|---------|
| `transcribe` | `(audio_chunk: bytes)` | `dict` |
| `synthesize` | `(text: str, voice: str, speaker_id: str)` | `bytes` |

### Strategy Pattern

| Interface | Implementações |
|-----------|---------------|
| STTStrategy | DeepgramSTT, WhisperSTT |
| TTSStrategy | PiperTTS, WavFallback |
| LLMStrategy | OllamaLLM |

## Fluxo Principal (STT)

1. `stt_autofallback.transcribe()` recebe áudio — `src/services/stt_autofallback.py:10`
2. Tenta Deepgram com timeout de 500ms — `src/services/stt_autofallback.py:14-15`
3. Se timeout ou confidence <= 0.3, fallback para Whisper — `src/services/stt_autofallback.py:20`

## Fluxo Principal (TTS)

1. `tts_service.synthesize()` recebe texto + voz — `src/services/tts_service.py:10-15`
2. Piper TTS tenta síntese
3. Se falhar, `tts_fallback.synthesize()` retorna WAV local — `src/services/tts_fallback.py:13-17`

## Dependências

- `extraction` — entidades extraídas usadas em contexto de LLM
- `events` — resultados de STT publicados em stream

## Riscos e Lacunas

- 🟡 DEEPGRAM_API_KEY vazia por padrão — sistema opera sempre em fallback
- 🟡 Sem cache de resultados de STT para chunks idênticos
