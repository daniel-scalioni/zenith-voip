---
spec:
  component: recording-lifecycle
  layer: audio
  status: active
  version: 1.3.0
  language: python
  patterns: []
  inputs: [{name: stage, type: string, from: audio-workers}]
  outputs: [{name: lease, type: JSON file, to: recording-directory}]
  dependencies: []
  events_produced: []
  updated_at: 2026-08-18
---

# Lifecycle de Gravação, Design

API neutra: `acquire_lease`, `renew_lease`, `release_lease`, `has_valid_lease` e
`heartbeat_lease`. Escritas usam temporário interno sem `.tmp` de áudio e `os.replace` no mesmo
diretório. Parser valida versão, stage, owner e timestamp; nomes arbitrários não são leases.

`locked_call_directory` usa `flock(LOCK_EX)` em `.recording-lifecycle.lock`. Aquisição, renovação
e liberação de lease entram nessa seção crítica. O cleanup mantém o mesmo lock desde a primeira
leitura dos leases/candidatos até salvar o marcador ou concluir exclusões. O lock não substitui o
lease durável: ele apenas elimina TOCTOU entre processos que cooperam com o lifecycle.

Ao adquirir um lease, o lifecycle inspeciona todos os estágios dentro do mesmo lock. Um lease
válido de outro owner causa `LeaseBusyError`; leases de estágios distintos com o mesmo owner são
permitidos para uma operação composta. Assim, adquirir `.smb-processing` também reivindica o
diretório contra captura/conversão concorrentes, enquanto a conversão interna do SMB reutiliza o
owner já adquirido.

O estágio `transcription` usa a mesma exclusão cross-stage durante STT, persistência e publicação.
Quando banco e destino remoto já comprovam conclusão mas o marcador local não existe, o worker
entra em `locked_call_directory`, revalida a presença do diretório e grava
`.consumed-transcription`. Esse reparo fecha a janela de falha entre publicação e marcação sem
duplicar transcrições.
