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

# Lifecycle de Gravação

- Aceitar somente leases `.capture-processing`, `.conversion-processing` e `.smb-processing`.
- Escrever JSON versionado atomicamente com owner UUID, call id, stage e expiração UTC.
- Renovar somente pelo owner; validade padrão 120 s e heartbeat padrão 30 s.
- Lease ausente, expirado ou corrompido não protege; release é idempotente e owner-safe.
- Todo arquivo com `.tmp` é parcial e jamais pode ser promovido por cleanup.
