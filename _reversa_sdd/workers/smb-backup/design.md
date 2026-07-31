---
spec:
  component: smb-backup
  layer: workers
  status: active
  version: 1.1.0
  language: python
  patterns: [strategy, singleton-module, observer]
  inputs:
    - {name: recordings, type: "tx.mp3 + rx.mp3", from: audio-uploader}
    - {name: call_metadata, type: Call, from: services-calls}
  outputs:
    - {name: stereo_audio, type: "MP3 stereo", to: smb-storage}
    - {name: transfer_state, type: JSON, to: smb-transfer-log}
  dependencies:
    - {component: audio-uploader, layer: workers}
    - {component: audio-cleanup, layer: workers}
    - {component: calls, layer: services}
    - {component: telemetry, layer: observability}
  events_produced: []
  updated_at: 2026-07-29
---

# SMB Backup de Áudio

## Objetivo

Publicar cada chamada concluída em storage SMB como um MP3 estéreo separável, com `tx` no canal
esquerdo e `rx` no direito, sem bloquear a gravação e sem expor arquivo remoto parcial.

## Contrato de entrada

- Layout: `/data/recordings/{tenant_id}/{call_id}/{tx,rx}.mp3`.
- Os monos finais existem somente depois de rename atômico pelo uploader.
- Se um `.raw` persistir, a conversão é retentada antes da composição.
- Metadados vêm de `Call.started_at`, `caller_number` e `callee_number`; ausência usa mtime e
  `desconhecido`.

## Contrato de saída

```text
{SMB_PATH}/{tenant_id}/{YYYY-MM-DD}/
  {YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id[0:6]}-{origem}-{destino}.mp3
```

- MP3 com dois canais: left=`tx`, right=`rx`.
- Colisão divergente tenta uma vez sufixo `call_id[6:10]`; nova colisão falha sem overwrite.
- Publicação remota: `.tmp`, chunks de 512 KiB por `storeFileFromOffset`, rename e SHA256.
- Primeiro chunk usa `offset=0, truncate=True`; demais usam offset crescente e `truncate=False`.

## Estado e idempotência

- Log: `/data/smb_logs/smb_transfer_log.json`.
- Estados: `pending`, `done`, `failed`.
- Chave lógica: `tenant_id + call_id`.
- Escrita local atômica por temporário no mesmo diretório e `os.replace`.
- JSON vazio/corrompido é isolado para diagnóstico; o worker inicia estado seguro e alerta.
- Entrada `done` é podada após sete dias; `failed` permanece sete dias.

## Concorrência e retenção

- Um único processo `zenith-smb-sync`, uma operação SMB por vez.
- O worker consome exclusivamente a fila ARQ `zenith:smb-sync`; não usa `arq:queue` e não pode
  retirar jobs de uploader ou cleanup.
- Ciclo simultâneo retorna `already_running`.
- Durante geração/cópia, `.smb-processing` registra lease UTC válido por 120 s, renovado a cada
  30 s.
- Cleanup ignora lease válido. Lease expirado, inválido ou corrompido é tratado como expirado e
  gera alerta.
- `stereo.mp3` é removido somente após checksum remoto confirmado. Os monos permanecem até a
  retenção local de aproximadamente duas horas.

## Resiliência

- Orçamento global de 30 s cobre geração estéreo, upload, leitura e checksum por chamada.
- Falha transitória: retry com esperas 1 s, 2 s e 4 s.
- Cinco falhas consecutivas abrem circuit breaker por cinco minutos.
- Configuração/autenticação inválida não recebe retry rápido.
- SMB indisponível nunca interrompe gravação local.

## Segurança e configuração

- Configuração vem exclusivamente de `Settings`/`.env`; `SMB_ENABLED=false` é o default.
- Direct TCP/445, NTLMv2 e `SMB_SIGN_OPTIONS=2` são defaults.
- Username, password e representação da conexão nunca entram em logs.
- Conta Zenith tem WRITE; credencial separada de auditoria é READ-ONLY e não entra no Zenith.

## Observabilidade

- Logs estruturados: tenant, call, status, bytes, latência, tentativa e classe sanitizada do erro.
- Métricas sem labels de alta cardinalidade: sucesso, falha, latência, fila e conversão pendente.

## Critérios de aceite

1. Testes Red antecedem cada implementação e cobertura nova é pelo menos 80%.
2. O arquivo remoto nunca aparece parcial e seu SHA256 coincide com o estéreo local.
3. Os canais podem ser extraídos separadamente sem mistura.
4. Timeout, lock, lease, retry, circuit breaker, colisão e recuperação do log têm testes.
5. O spike real com `pysmb==1.2.14` confirma Direct TCP, assinatura, offsets, rename e SHA256.
6. Recursos Docker novos usam prefixo `zenith-`/`zenith_`.
7. Uploader, cleanup e SMB sync usam filas ARQ exclusivas e um teste prova que nenhum job é
   consumido por worker que não registra sua função.

## Evidência de implementação — 2026-07-28

- `pysmb==1.2.14` confirmou Direct TCP/445, assinatura, offsets, rename, SHA256 e cleanup no
  storage real.
- `SMBBackupStrategy` final confirmou checksum do temporário antes do rename e checksum final.
- Throttle real: 2 MiB com limite de 1 MiB/s em 2,67 s.
- Estéreo sintético: 8 kHz/2 canais; left preservou 440 Hz (`tx`) e right 880 Hz (`rx`).
- 43 testes focados/regressivos passaram; `smb_sync.py` e `audio_uploader.py` ficaram acima de 80%
  de cobertura.
- Veredito independente corrigiu cancelamento de ffmpeg, checksum pré-rename e observabilidade de
  renovação do lease.

## Gates operacionais pendentes

- Provar ACL negativa com a conta READ-ONLY dos auditores.
- Executar Compose e suíte de infraestrutura no host com Docker/PostgreSQL/Redis disponíveis.
- Executar `alembic upgrade head` com PostgreSQL acessível.
- Implementar e redeployar o isolamento das filas ARQ aprovado em 2026-07-29. Como o produtor
  `upload_recording_batch` é carregado pelos processos FastAPI, o deploy deve incluir rolling
  restart das duas APIs, além da recriação dos três workers; reiniciar somente os workers deixa o
  produtor antigo publicando em `arq:queue`.
- Repetir E2E com uma nova chamada; não recuperar o payload do job falho anterior.

## Achado E2E — 2026-07-29

A chamada real chegou ao ESL, criou a linha `Call`, abriu o WebSocket e enfileirou
`upload_recording_batch`. O job falhou antes de criar `tx.mp3`/`rx.mp3` porque outro worker,
conectado à mesma fila default, o consumiu sem registrar a função. A causa raiz foi confirmada
pela inspeção do resultado ARQ: `JobExecutionFailed: function 'upload_recording_batch' not found`.
Decisão SDD: filas exclusivas `zenith:audio-upload`, `zenith:audio-cleanup` e `zenith:smb-sync`.
