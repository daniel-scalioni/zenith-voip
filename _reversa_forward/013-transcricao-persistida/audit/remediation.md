# Remediação do cross-check da Feature 013

> Data: 2026-08-18

| Achado histórico | Resolução |
|------------------|----------|
| A001 — contrato MP3/WAV incompatível | Resolvido pela feature 014 e pela 013 consumindo WAV PCM16 mono 16 kHz validado por header. |
| A002 — referências externas não ancoradas | Resolvido por specs SDD `transcript-batch`, `recording-lifecycle`, `audio-cleanup` e interfaces atualizadas. |
| A003 — adapter Whisper incompleto | Resolvido com `$PATH`, `-ojf`, parser validado, tokens/`avg_logprob`, timeout e cancelamento. |
| A004 — lifecycle/consumidor incompleto | Resolvido com estágio `transcription`, heartbeat, marker, reparo e política de capacidade. |
| A005 — validação real ausente | Gates automatizados concluídos; chamada real permanece no checkpoint T036 antes do fechamento final. |

O cross-check original permanece como registro histórico; esta matriz é o estado de remediação.
