---
spec:
  component: esl-integration
  layer: telephony
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton-module, observer]
  inputs: [{name: esl_events, type: event, from: freeswitch}]
  outputs: [{name: lifecycle_calls, type: async-call, to: audio-ingestion}]
  dependencies: [{component: audio-ingestion, layer: audio}]
  events_produced: [CHANNEL_ANSWER, CHANNEL_HANGUP]
  updated_at: 2026-08-14
---

# ESL Integration, Design

Somente a instância 1 processa ESL. `CHANNEL_ANSWER` registra metadata e envia o comando literal
`stereo 16000`. `CHANNEL_HANGUP` finaliza o registro de chamada e delega a publicação dos arquivos
a `AudioIngestor.finalize_stream`; não acessa buffers nem bytes de áudio.

Reconexão ESL, mappings SIP com TTL e vínculo manual `*88` permanecem inalterados.
