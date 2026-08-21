---
spec:
  component: audio-ingestion
  layer: audio
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton-module, observer]
  inputs: [{name: stereo_pcm16, type: bytes, from: mod-audio-stream}]
  outputs: [{name: finalized_recording, type: paths, to: audio-uploader}]
  dependencies: [{component: recording-lifecycle, layer: audio}, {component: recording-capacity, layer: audio}]
  events_produced: [audio_chunk]
  updated_at: 2026-08-14
---

# Ingestão de Áudio, Design

`AudioIngestor` mantém estado por chamada com metadata, handles, owner do lease e reserva. O
callback WebSocket valida/admite antes de `accept()`, cria o lease e abre arquivos sob demanda.
Não há `await` entre reivindicar o estado e escrever um chunk.

`finalize_stream(call_id)` reivindica o estado por `pop` antes de qualquer `await`, tornando
hangup/finally idempotentes. Cada handle é fechado e cada `.tmp.raw` íntegro é publicado como
`.raw`; o job recebe somente `tenant_id` e `call_id`. Falha de I/O encerra a gravação, preserva
qualquer temporário descartável e emite telemetria sem derrubar o SIP.

O singleton de módulo `audio_ingestor` continua sendo a integração usada por API e ESL.
