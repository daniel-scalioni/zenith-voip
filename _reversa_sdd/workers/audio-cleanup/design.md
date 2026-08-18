---
spec:
  component: audio-cleanup
  layer: workers
  status: active
  version: 2.2.0
  language: python
  patterns: [singleton-module]
  inputs: [{name: recordings, type: filesystem, from: audio-uploader}]
  outputs: [{name: cleanup_result, type: dict, to: arq}]
  dependencies: [{component: recording-consumers, layer: workers}, {component: recording-lifecycle, layer: audio}]
  events_produced: []
  updated_at: 2026-08-18
---

# Cleanup de Áudio, Design

Cada diretório de chamada é processado isoladamente. Lease válido protege todo o diretório.
`tx.wav`/`rx.wav` plenamente consumidos são removidos na rodada. O cutoff remove finais antigos
como rede de segurança, exceto os WAVs que ainda aguardam o consumidor obrigatório
`transcription`; esses permanecem backlog elegível enquanto o filesystem estiver acima de
`RECORDING_RESUME_FREE_PERCENT`. Abaixo dessa margem, o cutoff volta a valer para liberar backlog
vencido e preservar a captura de chamadas novas. Temporários reconhecidos usam
`.cleanup-candidates.json`, escrito atomicamente, contendo `first_seen` e
`(inode,size,mtime_ns)`.

O marcador é estado de observação, não prova de inatividade. A segunda rodada repete todas as
checagens e usa exclusão idempotente. Controles nunca entram na política por TTL.

Todo o processamento de um diretório ocorre dentro de `locked_call_directory`, compartilhado com
as mutações de lease. Um lease válido remove `.cleanup-candidates.json` antes de encerrar a
rodada. Cada entrada do marcador é validada como objeto; valores `null`, escalares ou listas são
ignorados e reconstruídos como primeira observação.
