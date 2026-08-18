---
spec:
  component: recording-lifecycle
  layer: audio
  status: active
  version: 1.2.0
  language: python
  patterns: []
  inputs: [{name: stage, type: string, from: audio-workers}]
  outputs: [{name: lease, type: JSON file, to: recording-directory}]
  dependencies: []
  events_produced: []
  updated_at: 2026-08-17
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
