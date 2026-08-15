---
spec:
  component: recording-consumers
  layer: workers
  status: active
  version: 1.0.0
  language: python
  patterns: []
  inputs: [{name: confirmation, type: consumer-name, from: recording-consumer}]
  outputs: [{name: consumed-state, type: boolean, to: audio-cleanup}]
  dependencies: []
  events_produced: []
  updated_at: 2026-08-14
---

# Consumidores de Gravação, Design

Módulo puro de filesystem com nomes restritos a `[a-z0-9_-]+`. O marcador contém JSON mínimo e
é publicado por `os.replace`. O cleanup apenas consulta a interseção entre configuração e arquivos.
