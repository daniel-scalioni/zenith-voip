---
spec:
  component: transcript-batch-design
  layer: workers
  status: active
  version: 1.0.0
  language: python
  patterns: [strategy, repository]
  inputs: [{name: ready_call_directory, type: Path, from: recordings-tmpfs}]
  outputs: [{name: persisted_transcript, type: Transcript, to: postgres-smb}]
  dependencies:
    - {component: transcript-batch, layer: workers}
  events_produced: []
  updated_at: 2026-08-18
---

# Design

`run_transcript_cycle` lista chamadas prontas e resolve metadados no schema do tenant. Sob lease
`transcription`, `process_call` cria chunks temporários, chama `WhisperCppSTT` sequencialmente,
normaliza segmentos, persiste tudo em uma transação, renderiza o Markdown e o publica pelo port
SMB existente. O diretório temporário de chunks é sempre removido.

O polling consulta o SMB com uma listagem por chamada/diretório e não baixa o `.md`. Se somente o
banco ou somente o SMB estiver concluído, a chamada é reprocessada para convergir as duas saídas.
Timeout cancela subprocessos e libera o lease no `finally`.
