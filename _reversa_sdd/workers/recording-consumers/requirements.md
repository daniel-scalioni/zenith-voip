---
spec:
  component: recording-consumers
  layer: workers
  status: active
  version: 1.0.0
  language: python
  patterns: []
  inputs: [{name: confirmation, type: consumer-name, from: recording-consumer}]
  outputs: [{name: marker, type: file, to: recording-directory}]
  dependencies: []
  events_produced: []
  updated_at: 2026-08-14
---

# Consumidores de Gravação

- `mark_consumed` cria atomicamente `.consumed-<consumer>` para nome validado.
- `is_fully_consumed` exige todos os consumidores configurados; lista vazia não autoriza exclusão.
- A feature 014 inicia com `smb`; consumidores futuros aderem por configuração e marcador.
