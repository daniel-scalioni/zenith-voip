---
spec:
  component: recording-capacity
  layer: audio
  status: active
  version: 1.0.0
  language: python
  patterns: []
  inputs: [{name: disk_usage, type: bytes, from: recording-tmpfs}]
  outputs: [{name: admission, type: boolean, to: audio-ingestion}]
  dependencies: []
  events_produced: []
  updated_at: 2026-08-14
---

# Capacidade de Gravação

- Reservar 19.200.000 bytes por chamada de até 300 s, descontando crescimento já materializado.
- Somar 128 MiB de headroom de processamento à projeção.
- Recusar nova gravação que deixe menos de 20% livre; manter modo degradado até 30% livre.
- Nunca interromper gravações ativas; release é idempotente.
- A decisão afeta somente captura, não sinalização/mídia SIP.
