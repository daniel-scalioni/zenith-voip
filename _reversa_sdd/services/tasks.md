# Services, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar interface Strategy e Repository
  - Origem: `src/services/base.py`
  - Critério: STTStrategy, TTSStrategy, LLMStrategy, GenericRepository definidos
  - Confiança: 🟢

- [ ] T-02, Implementar STT Deepgram
  - Origem: `src/services/stt_deepgram.py`
  - Critério: transcrição via Deepgram nova-2, português, diarizado
  - Confiança: 🟢

- [ ] T-03, Implementar STT Whisper (fallback)
  - Origem: `src/services/stt_whisper.py`
  - Critério: transcrição via Whisper.cpp
  - Confiança: 🟢

- [ ] T-04, Implementar AutoFallback STT
  - Origem: `src/services/stt_autofallback.py`
  - Critério: fallback para Whisper se timeout > 500ms ou confidence <= 0.3
  - Confiança: 🟢

- [ ] T-05, Implementar TTS Piper
  - Origem: `src/services/tts_service.py`
  - Critério: síntese de voz via Piper TTS
  - Confiança: 🟢

- [ ] T-06, Implementar fallback TTS WAV local
  - Origem: `src/services/tts_fallback.py`
  - Critério: WAV local tocado se Piper falhar
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar STT com Deepgram (sucesso)
- [ ] TT-02, Testar fallback STT (Deepgram timeout → Whisper)
- [ ] TT-03, Testar TTS Piper
- [ ] TT-04, Testar fallback TTS
