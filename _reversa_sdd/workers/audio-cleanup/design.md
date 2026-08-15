---
spec:
  component: audio-cleanup
  layer: workers
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton-module]
  inputs: [{name: recordings, type: filesystem, from: audio-uploader}]
  outputs: [{name: cleanup_result, type: dict, to: arq}]
  dependencies: [{component: recording-consumers, layer: workers}, {component: recording-lifecycle, layer: audio}]
  events_produced: []
  updated_at: 2026-08-14
---

# Cleanup de Áudio, Design

Cada diretório de chamada é processado isoladamente. Lease válido protege todo o diretório.
`tx.wav`/`rx.wav` plenamente consumidos são removidos na rodada; arquivos finais mais antigos que
o cutoff também são removidos. Temporários reconhecidos usam `.cleanup-candidates.json`, escrito
atomicamente, contendo `first_seen` e `(inode,size,mtime_ns)`.

O marcador é estado de observação, não prova de inatividade. A segunda rodada repete todas as
checagens e usa exclusão idempotente. Controles nunca entram na política por TTL.
