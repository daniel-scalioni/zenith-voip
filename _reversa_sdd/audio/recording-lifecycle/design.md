---
spec:
  component: recording-lifecycle
  layer: audio
  status: active
  version: 1.0.0
  language: python
  patterns: []
  inputs: [{name: stage, type: string, from: audio-workers}]
  outputs: [{name: lease, type: JSON file, to: recording-directory}]
  dependencies: []
  events_produced: []
  updated_at: 2026-08-14
---

# Lifecycle de Gravação, Design

API neutra: `acquire_lease`, `renew_lease`, `release_lease`, `has_valid_lease` e
`heartbeat_lease`. Escritas usam temporário interno sem `.tmp` de áudio e `os.replace` no mesmo
diretório. Parser valida versão, stage, owner e timestamp; nomes arbitrários não são leases.
