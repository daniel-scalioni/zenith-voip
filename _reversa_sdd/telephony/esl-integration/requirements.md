---
spec:
  component: esl-integration
  layer: telephony
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton-module, observer]
  inputs: [{name: esl_events, type: event, from: freeswitch}]
  outputs: [{name: audio_stream_command, type: command, to: mod-audio-stream}]
  dependencies: [{component: audio-ingestion, layer: audio}]
  events_produced: [CHANNEL_ANSWER, CHANNEL_HANGUP]
  updated_at: 2026-08-14
---

# Integração ESL

- Iniciar captura com `uuid_audio_stream <id> start <url> stereo 16000 <metadata>`.
- Registrar metadata antes da captura e finalizar o stream no `CHANNEL_HANGUP`.
- A finalização é idempotente com a desconexão WebSocket e não reagrupa áudio em memória.
- Falha ao iniciar/finalizar gravação não derruba nem altera sinalização/mídia SIP.
