---
spec:
  component: audio-cleanup
  layer: workers
  status: active
  version: 2.1.0
  language: python
  patterns: [singleton-module]
  inputs: [{name: recordings, type: filesystem, from: audio-uploader}]
  outputs: [{name: cleanup_result, type: dict, to: arq}]
  dependencies: [{component: recording-consumers, layer: workers}, {component: recording-lifecycle, layer: audio}]
  events_produced: []
  updated_at: 2026-08-17
---

# Cleanup de Áudio, Design

Cada diretório de chamada é processado isoladamente. Lease válido protege todo o diretório.
`tx.wav`/`rx.wav` plenamente consumidos são removidos na rodada; arquivos finais mais antigos que
o cutoff também são removidos. Temporários reconhecidos usam `.cleanup-candidates.json`, escrito
atomicamente, contendo `first_seen` e `(inode,size,mtime_ns)`.

O marcador é estado de observação, não prova de inatividade. A segunda rodada repete todas as
checagens e usa exclusão idempotente. Controles nunca entram na política por TTL.

Todo o processamento de um diretório ocorre dentro de `locked_call_directory`, compartilhado com
as mutações de lease. Um lease válido remove `.cleanup-candidates.json` antes de encerrar a
rodada. Cada entrada do marcador é validada como objeto; valores `null`, escalares ou listas são
ignorados e reconstruídos como primeira observação.
