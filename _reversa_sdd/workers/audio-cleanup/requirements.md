---
spec:
  component: audio-cleanup
  layer: workers
  status: active
  version: 2.2.0
  language: python
  patterns: [singleton-module]
  inputs: [{name: recordings, type: filesystem, from: audio-uploader}]
  outputs: [{name: deletion_metrics, type: metrics, to: observability}]
  dependencies: [{component: recording-consumers, layer: workers}, {component: recording-lifecycle, layer: audio}]
  events_produced: []
  updated_at: 2026-08-17
---

# Cleanup de Áudio

- Remover finais plenamente consumidos sem esperar TTL; manter TTL como rede de segurança.
- Quando `transcription` estiver na lista de consumidores exigidos, preservar `tx.wav`/`rx.wav`
  vencidos enquanto houver capacidade acima da margem de retomada. Sob pressão de capacidade,
  o TTL volta a ser a rede de segurança e descarta backlog vencido antes de recusar novas
  gravações; transcrição é best-effort e não pode esgotar o tmpfs.
- Tratar somente temporários locais allowlisted e nunca controles/leases ou temporário remoto.
- Na primeira rodada registrar fingerprint; após 900 s revalidar e então excluir se inalterado,
  sem lease e ainda temporário. Mudança ou lease reaparecido cancela candidatura.
- Tolerar marcador corrompido, desaparecimento de arquivo e dois cleanups concorrentes.
- Tratar entradas internas do marcador que não sejam objetos como observações inválidas, sem
  abortar o bucket. Lease reaparecido apaga a candidatura anterior sob o lock de lifecycle.
- Rodar a cada 15 min com job cron único na fila `zenith:audio-cleanup`.
