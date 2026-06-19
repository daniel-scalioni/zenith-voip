# Services — Serviços de IA

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Camada de serviços de IA com padrões Strategy e Repository: STT com fallback automático (Deepgram → Whisper), TTS com fallback (Piper → WAV local), e GenericRepository CRUD.

## Responsabilidades

- Transcrever áudio com fallback automático (Deepgram primário, Whisper fallback)
- Sintetizar voz via Piper TTS com fallback WAV local
- Prover repositório CRUD genérico

## Regras de Negócio

- Deepgram é o provider primário de STT 🟢
- Fallback para Whisper se timeout > 500ms 🟢
- Fallback também ocorre se confidence <= 0.3 🟢
- Modelo Deepgram: nova-2, português, diarizado 🟢
- Piper TTS é primário; se falhar, usa WAV local 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Transcrever áudio via Deepgram (primário) | Must |
| RF-02 | Fallback automático para Whisper em caso de timeout | Must |
| RF-03 | Fallback automático para Whisper se confidence baixa | Must |
| RF-04 | Sintetizar voz via Piper TTS | Must |
| RF-05 | Fallback para WAV local se Piper falhar | Should |
| RF-06 | Prover CRUD genérico via Repository | Must |

## Rastreabilidade

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `src/services/base.py` | Strategy, Repository, Factory interfaces | 🟢 |
| `src/services/stt_autofallback.py` | `transcribe()` | 🟢 |
| `src/services/stt_deepgram.py` | DeepgramSTT | 🟢 |
| `src/services/stt_whisper.py` | WhisperSTT | 🟢 |
| `src/services/tts_service.py` | `synthesize()` | 🟢 |
| `src/services/tts_fallback.py` | `synthesize()` (WAV local) | 🟢 |
