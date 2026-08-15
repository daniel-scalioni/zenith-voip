# Data Delta: Captura de áudio em WAV 16 kHz na origem

> Identificador: `014-captura-wav-16k`
> Data: `2026-08-12`

## 1. PostgreSQL

Nenhuma mudança. Nenhuma tabela, coluna, índice ou migração Alembic é necessária (D-13 no
`roadmap.md`). Confirmado contra `_reversa_sdd/erd-complete.md` e `_reversa_sdd/state-machines.md`
— a máquina de estados de `Call` (`in_progress` → `completed`) não ganha estado novo; o ciclo de
vida do arquivo de gravação é inteiramente externo ao banco, como já é hoje.

## 2. Filesystem — `RECORDINGS_PATH` (`zenith_recordings_tmpfs`)

### 2.1 Layout de diretório (inalterado)

```
RECORDINGS_PATH/<tenant_id>/<call_id>/
```

### 2.2 Arquivos por chamada — antes vs. depois

| Arquivo | Antes (legado) | Depois (esta feature) | Observação |
|---|---|---|---|
| `tx.tmp.raw` / `rx.tmp.raw` | Não existe | **Novo** — nome transitório do canal enquanto a chamada está ativa; escrito incrementalmente, chunk a chunk, conforme chega do WebSocket | RN-09/RF-09, D-03/D-14 |
| `tx.raw` / `rx.raw` | Escrito de uma vez no hangup, a partir de bytes acumulados em RAM | Só passa a existir com este nome na finalização (`os.replace` de `.tmp.raw`), quando a chamada já terminou | RN-09/RF-09, D-04/D-14 — mesmo nome final de antes, ciclo de vida diferente |
| `tx.tmp.wav` / `rx.tmp.wav` | `tx.tmp.mp3` / `rx.tmp.mp3` durante conversão | **Novo contrato WAV** — saída privada do ffmpeg; só vira `tx.wav`/`rx.wav` por `os.replace` após sucesso | RN-10/RF-10, D-02 |
| `tx.mp3` / `rx.mp3` | Canal mono, 8 kHz, MP3 (lossy) | **Substituído por** `tx.wav` / `rx.wav`, canal mono, 16 kHz, PCM16 | RN-02, D-02 |
| `stereo.tmp.wav` → `stereo.wav` | `stereo.tmp.mp3` → `stereo.mp3` | Estéreo derivado PCM16 16 kHz; nome final só aparece após mixagem íntegra | RN-08/RN-10, D-07 |
| `.capture-processing` | Não existe | **Novo** — lease renovável durante captura de `.tmp.raw` | RN-11, D-16/D-17 |
| `.conversion-processing` | Não existe | **Novo** — lease renovável/exclusivo durante `.raw → .wav` | RN-11, D-05/D-16 |
| `.smb-processing` | Lease hardcoded do SMB | Mantido, mas passa a usar a API genérica de leases nomeados | D-16 |
| `.consumed-<consumer>` | Não existe | **Novo** — um arquivo vazio (ou com timestamp) por consumidor confirmado, ex. `.consumed-smb` | RF-08, D-09/D-11 |
| `.cleanup-candidates.json` | Não existe | **Novo** — estado persistente da primeira rodada para temporários órfãos locais | RN-12/RF-11, D-18 |

Um marcador estático `.call-active` foi cogitado e descartado — ver `investigation.md#6`. O nome
transitório impede consumo prematuro; o lease renovável `.capture-processing` resolve a questão
diferente de provar atividade ao cleanup sem depender do `mtime` do áudio.

### 2.3 Novo artefato: marcador de confirmação de consumo

- **Nome:** `.consumed-<consumer>` (ex.: `.consumed-smb`)
- **Conteúdo:** JSON mínimo, mesmo padrão de `write_lease` (`smb_sync.py:177-193`) —
  `{"consumer": "smb", "confirmed_at": "<ISO8601 UTC>"}`
- **Escrita:** atômica (`tmp` + `os.replace`), mesmo padrão de todo write-then-rename já usado no
  projeto (RN-05)
- **Ciclo de vida:** criado quando o consumidor confirma consumo; removido junto com o diretório
  da chamada quando `audio_cleanup` executa a exclusão (não precisa de remoção própria — o
  diretório inteiro é limpo por arquivo, e o marcador para de ter função quando `tx.wav`/`rx.wav`
  já não existem)
- **Consumidores exigidos:** `settings.RECORDING_REQUIRED_CONSUMERS: list[str] = ["smb"]` — a
  `013` se soma a esta lista via configuração quando for mergeada (D-10), não via código

## 3. `smb_transfer_log.json` (`SMB_TRANSFER_LOG_PATH`)

Estrutura inalterada — apenas os valores de três campos passam a apontar para `.wav`:

```diff
  {
    "tenant_id": "...",
    "call_id": "...",
-   "tx_path": ".../tx.mp3",
-   "rx_path": ".../rx.mp3",
-   "stereo_path": ".../stereo.mp3",
+   "tx_path": ".../tx.wav",
+   "rx_path": ".../rx.wav",
+   "stereo_path": ".../stereo.wav",
    "status": "done",
    ...
  }
```

Nenhuma migração de log é necessária: o `smb_transfer_log.json` é reconstruído por chamada nova, e
a inspeção do host confirmou que não há chamadas pendentes de migrar no corte.

## 4. Configuração (`src/config.py`)

| Campo novo | Tipo | Default | Origem |
|---|---|---|---|
| `RECORDING_REQUIRED_CONSUMERS` | `list[str]` | `["smb"]` | D-10 — lista de consumidores que `audio_cleanup` exige confirmados antes de excluir por consumo (RF-08) |
| `RECORDING_MAX_CALL_SECONDS` | `int` | `300` | D-20 — reserva máxima por gravação admitida |
| `RECORDING_MIN_FREE_PERCENT` | `float` | `20` | D-20 — entrada no modo degradado |
| `RECORDING_RESUME_FREE_PERCENT` | `float` | `30` | D-20 — saída com histerese |
| `RECORDING_PROCESSING_HEADROOM_BYTES` | `int` | `134217728` | D-20 — reserva fixa para conversões/mixagem e metadados |
| `RECORDING_LEASE_TTL_SECONDS` | `int` | `120` | D-17 — validade do lease renovável |
| `RECORDING_LEASE_HEARTBEAT_SECONDS` | `int` | `30` | D-17 — cadência de renovação |
| `RECORDING_CLEANUP_ROUND_SECONDS` | `int` | `900` | D-18 — intervalo mínimo entre detecção e exclusão de órfão |

Nenhum campo existente muda de tipo ou default. `AUDIO_RETENTION_DAYS` (default `90`, valor
operacional real `0.0833` via env, `docker-compose.app.yml:183`) continua existindo, agora como
rede de segurança (RN-07), não como gatilho primário.

## 5. Capacidade — projeção de ocupação (informativo, não é mudança de esquema)

| Métrica | Antes (MP3 8 kHz) | Depois (WAV 16 kHz) |
|---|---|---|
| Estimativa por hora-chamada (dois canais mono, arquivo final) | ~29 MB/h (🟡, `docker-compose.app.yml`) | ~230 MB/h (🟡, mesma fonte) |
| Tamanho do `zenith_recordings_tmpfs` | 512 MB | **2 GiB** (D-21) |
| Defesa primária contra estouro | TTL (~2h) | Confirmação de consumo + admissão com reserva/histerese + cleanup de órfãos; TTL como rede final |

### 5.1 Pico de coexistência (não é a mesma coisa que o total por chamada)

A tabela acima mostra o tamanho do artefato final por chamada, não o pico de ocupação
simultânea — que é maior porque, em dois momentos distintos do ciclo de vida de uma mesma
chamada, dois artefatos com conteúdo de áudio equivalente coexistem no tmpfs antes de o mais
antigo ser removido:

| Janela | Arquivos coexistindo | Estimativa (chamada de 5 min) |
|---|---|---|
| Captura | `tx.tmp.raw`+`rx.tmp.raw` | ~19,2 MB por chamada; 30 chamadas ≈ 576 MB |
| Conversão ARQ (máximo padrão de 10 jobs) | arquivos estáveis (~576 MB por coorte cheia) + até um canal `.tmp.wav` por job | acréscimo aproximado de 96 MB; pico estimado ~672 MB |
| Publicação SMB sequencial | `tx.wav`+`rx.wav` da coorte + um `stereo.tmp.wav` | acréscimo aproximado de 19,2 MB |

O limite operacional não é derivado apenas dessa coorte: backlog SMB e temporários aguardando a
segunda rodada também ocupam o volume. Por isso 2 GiB é acompanhado por admissão que considera
uso real e crescimento restante, headroom fixo de processamento, alerta e gate real de 20%.

## 6. Temporário remoto SMB

`<final>.wav.tmp` vive no compartilhamento remoto e não é visível ao `audio_cleanup` local. O
`smb_transfer_log.json` passa a registrar a primeira observação de temporário remoto sem upload
ativo. Na observação seguinte, após ao menos um intervalo de sincronização, o worker SMB remove o
órfão. Um upload com `.smb-processing` válido nunca é coletado.
