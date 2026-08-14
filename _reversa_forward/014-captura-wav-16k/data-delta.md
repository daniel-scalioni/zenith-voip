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
| `tx.mp3` / `rx.mp3` | Canal mono, 8 kHz, MP3 (lossy) | **Substituído por** `tx.wav` / `rx.wav`, canal mono, 16 kHz, PCM16 | RN-02, D-02 |
| `stereo.mp3` (transitório) | Estéreo derivado, 8 kHz, MP3, existe só durante o ciclo de publicação SMB | **Substituído por** `stereo.wav`, estéreo, 16 kHz, PCM16, mesmo ciclo de vida transitório | RN-08, D-07 |
| `.smb-processing` (lease) | Inalterado | Inalterado | Sem mudança nesta feature |
| `.consumed-<consumer>` | Não existe | **Novo** — um arquivo vazio (ou com timestamp) por consumidor confirmado, ex. `.consumed-smb` | RF-08, D-09/D-11 |

Um marcador de "chamada ativa" separado (`.call-active`) foi cogitado e descartado nesta revisão
— ver `investigation.md#6`. O nome transitório `tx.tmp.raw`/`rx.tmp.raw` já cumpre esse papel por
construção, sem exigir um segundo arquivo de estado.

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

Nenhum campo existente muda de tipo ou default. `AUDIO_RETENTION_DAYS` (default `90`, valor
operacional real `0.0833` via env, `docker-compose.app.yml:183`) continua existindo, agora como
rede de segurança (RN-07), não como gatilho primário.

## 5. Capacidade — projeção de ocupação (informativo, não é mudança de esquema)

| Métrica | Antes (MP3 8 kHz) | Depois (WAV 16 kHz) |
|---|---|---|
| Estimativa por hora-chamada (dois canais mono, arquivo final) | ~29 MB/h (🟡, `docker-compose.app.yml`) | ~230 MB/h (🟡, mesma fonte) |
| Tamanho do `zenith_recordings_tmpfs` | 512 MB | 512 MB (inalterado nesta feature) |
| Defesa primária contra estouro | TTL (~2h) | Confirmação de consumo (RF-08), TTL como rede de segurança |

### 5.1 Pico de coexistência (não é a mesma coisa que o total por chamada)

A tabela acima mostra o tamanho do artefato final por chamada, não o pico de ocupação
simultânea — que é maior porque, em dois momentos distintos do ciclo de vida de uma mesma
chamada, dois artefatos com conteúdo de áudio equivalente coexistem no tmpfs antes de o mais
antigo ser removido:

| Janela | Arquivos coexistindo | Estimativa (chamada de 1h, 🟡) |
|---|---|---|
| Conversão (logo após o hangup) | `tx.raw`+`rx.raw` (prestes a ser removidos) **+** `tx.wav`+`rx.wav` (recém-criados) | ~230 MB + ~230 MB ≈ **460 MB** |
| Publicação SMB (posterior, assíncrona) | `tx.wav`+`rx.wav` **+** `stereo.wav` (mesmo conteúdo de áudio, layout estéreo) | ~230 MB + ~230 MB ≈ **460 MB** |

Nenhuma das duas janelas depende de concorrência entre chamadas — uma única chamada de 1h já
chega a ~90% do tmpfs de 512 MB no pico, sozinha. RF-08 (exclusão por confirmação de consumo)
não ajuda dentro dessas janelas: a confirmação só pode existir *depois* que a janela de
publicação termina, que é justamente o momento do segundo pico. Ver risco correspondente em
`roadmap.md#9` e o passo de medição em `onboarding.md#8`.
