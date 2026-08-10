---
spec:
  component: smb-audio-backup-addendum
  layer: workers
  status: active
  version: 1.0.0
  language: python
  patterns: [strategy, event-driven]
  inputs: [{name: local_call_recordings, type: mp3_pair, from: audio-uploader}]
  outputs: [{name: remote_recording, type: stereo_mp3, to: smb-storage}]
  dependencies: [{component: audio-uploader, layer: workers}, {component: call-records, layer: services}]
  events_produced: []
  updated_at: 2026-08-01
---

# Adendo 011 — Backup SMB de áudio

## Origem

- Feature: `011-smb-audio-backup`
- Entrega convergida em: `2026-08-01`
- Artefatos detalhados: `_reversa_forward/011-smb-audio-backup/`

## Delta vigente

- Cada gravação concluída com `tx.mp3` e `rx.mp3` é combinada em MP3 estéreo separável e publicada no SMB por tenant e data.
- A publicação é assíncrona, idempotente e isolada da cadeia crítica de gravação, com checksum, retry, circuit breaker, throttle, lock de ciclo e lease contra cleanup concorrente.
- Uploader, cleanup e sincronização SMB usam filas ARQ exclusivas.
- O produtor publica o upload explicitamente em `zenith:audio-upload`.
- `caller_number` e `callee_number` existentes passam a receber os metadados disponíveis no evento ESL.
- A baseline Alembic é restrita ao schema `public`; schemas de tenant continuam sendo provisionados explicitamente.
- Banco de teste, rehearsal e candidato usam recursos exclusivos com prefixo `zenith-`, sem reutilizar o PostgreSQL operacional.
- Credenciais SMB permanecem exclusivamente em configuração privada e não fazem parte dos artefatos versionados.

## Evidência de aceite

- Suite final: 188 testes aprovados, 12 integrações externas explicitamente ignoradas e cobertura total de 86,01%.
- 45 testes PostgreSQL reais aprovados em ambiente isolado.
- Baseline Alembic aplicada e validada duas vezes.
- Chamada real `1001 → 1140100` concluída e persistida no banco candidato.
- Upload e cópia SMB concluídos; checksum confirmado; áudio remoto reproduzido e aprovado pelo usuário.
- Revisões independentes de Claude/Sonnet, OpenCode DeepSeek e OpenCode Mimo concluídas; bloqueios processuais corrigidos antes do aceite.
- PostgreSQL anterior preservado para rollback.

## Impactos que devem permanecer visíveis

- A indisponibilidade do SMB nunca pode interromper a gravação local.
- `tx.mp3` e `rx.mp3` continuam sendo as fontes mono; o estéreo é derivado e transitório localmente.
- O cleanup deve respeitar lease SMB válido.
- As três filas ARQ não podem voltar a compartilhar a fila padrão.
- Segredos SMB não podem aparecer em código, specs ou logs.
- O banco anterior não deve ser removido até decisão operacional explícita.

## Vigência

Vigente desde 2026-08-01.
