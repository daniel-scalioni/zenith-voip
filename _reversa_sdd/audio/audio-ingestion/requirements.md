---
spec:
  component: audio-ingestion
  layer: audio
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton-module, observer]
  inputs: [{name: stereo_pcm16, type: bytes, from: mod-audio-stream}]
  outputs: [{name: raw_channels, type: "tx.raw + rx.raw", to: audio-uploader}]
  dependencies: [{component: recording-lifecycle, layer: audio}, {component: recording-capacity, layer: audio}]
  events_produced: [audio_chunk]
  updated_at: 2026-08-14
---

# Ingestão de Áudio

## Requisitos

- Aceitar somente `call_id` previamente registrado pelo ESL; recusar desconhecido com 4401.
- Admitir nova gravação somente quando a projeção do tmpfs respeitar a margem configurada;
  recusar somente a gravação com 4403, sem interferir na chamada SIP.
- De-intercalar PCM16 estéreo 16 kHz em `tx` e `rx`, preservando a semântica dos canais.
- Criar `.capture-processing` antes de qualquer temporário e renová-lo enquanto o stream estiver ativo.
- Gravar cada chunk imediatamente em `tx.tmp.raw`/`rx.tmp.raw`, sem buffer proporcional à chamada.
- Finalizar uma única vez tanto no hangup quanto no `finally`: fechar handles, publicar `.raw` com
  `os.replace`, enfileirar paths, liberar lease/reserva e somente depois remover metadata.
- Ignorar chunks tardios e preservar metadata quando WebSocket e hangup chegam em qualquer ordem.
