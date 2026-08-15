---
spec:
  component: audio-cleanup
  layer: workers
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton-module]
  inputs: [{name: recordings, type: filesystem, from: audio-uploader}]
  outputs: [{name: deletion_metrics, type: metrics, to: observability}]
  dependencies: [{component: recording-consumers, layer: workers}, {component: recording-lifecycle, layer: audio}]
  events_produced: []
  updated_at: 2026-08-14
---

# Cleanup de Áudio

- Remover finais plenamente consumidos sem esperar TTL; manter TTL como rede de segurança.
- Tratar somente temporários locais allowlisted e nunca controles/leases ou temporário remoto.
- Na primeira rodada registrar fingerprint; após 900 s revalidar e então excluir se inalterado,
  sem lease e ainda temporário. Mudança ou lease reaparecido cancela candidatura.
- Tolerar marcador corrompido, desaparecimento de arquivo e dois cleanups concorrentes.
- Rodar a cada 15 min com job cron único na fila `zenith:audio-cleanup`.
