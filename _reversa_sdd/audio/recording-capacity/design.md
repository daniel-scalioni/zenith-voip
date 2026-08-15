---
spec:
  component: recording-capacity
  layer: audio
  status: active
  version: 1.0.0
  language: python
  patterns: []
  inputs: [{name: disk_usage, type: bytes, from: recording-tmpfs}]
  outputs: [{name: reservation, type: token, to: audio-ingestion}]
  dependencies: []
  events_produced: []
  updated_at: 2026-08-14
---

# Capacidade de Gravação, Design

`RecordingCapacityGuard` serializa admissão em `asyncio.Lock`, consulta `shutil.disk_usage` e
mantém reservas por call id. A projeção usa uso real + bytes restantes das ativas + nova reserva
+ headroom. O estado degradado entra no limite de 80% e só sai quando a projeção cai a 70%.
