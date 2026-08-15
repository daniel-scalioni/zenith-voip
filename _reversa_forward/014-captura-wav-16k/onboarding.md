# Onboarding: Captura de áudio em WAV 16 kHz na origem

> Identificador: `014-captura-wav-16k`
> Data: `2026-08-12`
> Público: quem for validar esta feature pela primeira vez, manualmente, contra o host de
> produção (`10.10.10.11`)

## 0. Pré-requisitos

- Acesso SSH ao host `10.10.10.11` (usuário `administrator`, chave `~/.ssh/id_ed25519` — ver
  `AGENTS.md#Credenciais-e-Segurança`)
- `ffprobe` disponível localmente (ou via `docker exec` num container que já tenha `ffmpeg`)
- Um ramal de teste registrado (ex.: `1001`) capaz de originar/receber uma chamada real
- Código desta feature já implantado nos containers `zenith-api-1`, `zenith-api-2`,
  `zenith-arq-uploader`, `zenith-arq-smb-sync` e `zenith-arq-cleanup`

## 1. Confirmar estado limpo antes de testar

```bash
ssh administrator@10.10.10.11 'df -h | grep recordings; find /data/recordings -maxdepth 3'
```

Esperado: tmpfs com baixa ocupação, sem `.mp3` remanescente (ou apenas diretórios de chamadas já
processadas por consumo/TTL). Se houver `.mp3` legado, isso é esperado ser ignorado sem erro
(RF-04) — não é bloqueio para seguir.

## 2. Originar uma chamada real e observar a captura em andamento

1. Fazer uma chamada real usando o ramal de teste (`1001 → 1140100` ou equivalente), mantendo-a
   ativa por pelo menos 30 segundos.
2. Durante a chamada (antes de desligar), verificar que `<channel>.tmp.raw` já existe e está
   crescendo em disco — evidência direta de RF-09 (escrita incremental, não acumulação em RAM).
   **Não use `tx.raw`/`rx.raw` (sem `.tmp`) para essa checagem** — esse nome só passa a existir
   depois do hangup, por desenho (D-14, ver `roadmap.md#3`):
   ```bash
   ssh administrator@10.10.10.11 \
     'watch -n 2 "ls -la /data/recordings/<tenant_id>/<call_id>/"'
   ```
   Esperado: `tx.tmp.raw` e `rx.tmp.raw` presentes, com `st_size` crescendo entre observações
   sucessivas.
3. (Opcional, evidência de RF-09 sobre memória) Observar o consumo de RAM do processo
   `fastapi-*` durante a chamada — não deve crescer de forma perceptível conforme a chamada se
   alonga.
4. **Medir a taxa efetiva (RF-01), não confiar só no rótulo do arquivo final.** `ffprobe` no
   `.wav` reportará `16000 Hz` porque foi isso que mandamos o `ffmpeg` escrever no header — isso
   não prova que o FreeSWITCH de fato enviou 16 kHz (um token não reconhecido poderia estar
   caindo no default de 8 kHz, e o `.wav` ficaria com metade das amostras reais tocando em
   velocidade dobrada, "efeito esquilo"). O discriminador real é vazão medida contra tempo de
   parede:
   ```bash
   ssh administrator@10.10.10.11 \
     'stat -c %s /data/recordings/<tenant_id>/<call_id>/tx.tmp.raw'
   # repetir após N segundos exatos (ex.: 10s) e comparar o delta de bytes
   ```
   PCM16 mono a 16 kHz produz **32000 bytes/s** por canal; a 8 kHz seriam **16000 bytes/s**. Se o
   delta medido ficar perto de 16000 bytes/s, o token `16000` não está sendo honrado pelo
   FreeSWITCH — reabrir D-01. Complementar ouvindo o `.wav` final: uma chamada capturada a 8 kHz
   e rotulada como 16 kHz toca com voz aguda e mais rápida que o original (evidência auditiva
   direta do mesmo problema).

## 3. Encerrar a chamada e validar o formato final

```bash
ssh administrator@10.10.10.11 'ls -la /data/recordings/<tenant_id>/<call_id>/'
```

Esperado: `tx.wav` e `rx.wav`. `tx.tmp.raw`/`rx.tmp.raw` não existem mais (viraram `tx.raw`/
`rx.raw` na finalização e depois foram consumidos pela conversão); não deve sobrar `.raw`
(sem `.tmp`) se a conversão terminou com sucesso.

```bash
ffprobe -hide_banner /data/recordings/<tenant_id>/<call_id>/tx.wav
ffprobe -hide_banner /data/recordings/<tenant_id>/<call_id>/rx.wav
```

Esperado em ambos: `Audio: pcm_s16le ..., 16000 Hz, mono`. Ouvir os dois arquivos (ou inspecionar
visualmente a forma de onda) para confirmar que `tx` tem a voz do atendente e `rx` a do cliente
(sem troca de canal), e que a velocidade/tom soam naturais (ver passo 2.4).

## 4. Validar o ciclo de backup SMB (WAV estéreo)

Disparar o ciclo manualmente em vez de esperar o cron (`zenith:smb-sync`, a cada
`SMB_SYNC_INTERVAL_MINUTES`):

```bash
docker exec zenith-arq-smb-sync python -c "
import asyncio
from src.workers.smb_sync import run_smb_sync
asyncio.run(run_smb_sync(None))
"
```

Verificar:
- `stereo.wav` foi criado localmente, publicado no SMB e removido localmente após checksum
- O arquivo remoto abre/reproduz normalmente (equipe de Qualidade consegue ouvir)
- `smb_transfer_log.json` (`SMB_TRANSFER_LOG_PATH`) tem `status: "done"` para essa chamada, com
  `tx_path`/`rx_path`/`stereo_path` apontando para `.wav`

## 5. Validar a exclusão por confirmação de consumo (RF-08), antes do TTL

Logo após o passo 4 confirmar `status: "done"`, checar que o marcador de consumo foi criado:

```bash
ssh administrator@10.10.10.11 'ls -la /data/recordings/<tenant_id>/<call_id>/'
```

Esperado: `.consumed-smb` presente.

Disparar o ciclo de cleanup manualmente (sem esperar o cron de 15 min):

```bash
docker exec zenith-arq-cleanup python -c "
import asyncio
from src.workers.audio_cleanup import run_cleanup
asyncio.run(run_cleanup(None))
"
```

Esperado: `tx.wav`/`rx.wav` dessa chamada removidos **mesmo que o `mtime` ainda esteja bem dentro
da janela de `AUDIO_RETENTION_DAYS`** — essa é a evidência de que a exclusão por confirmação, não
o TTL, foi o gatilho.

## 6. Validar a rede de segurança do TTL (caminho sem confirmação)

Repetir os passos 2-3 com o backup SMB **desabilitado** (`SMB_ENABLED=false` temporariamente, ou
interrompendo o worker `zenith-arq-smb-sync`) para uma chamada de teste isolada:

1. Confirmar que `tx.wav`/`rx.wav` existem e que nenhum `.consumed-*` é criado.
2. Rodar o cleanup manualmente (passo 5) antes do TTL expirar — esperado: os arquivos
   **permanecem**.
3. Esperar o TTL configurado (`AUDIO_RETENTION_DAYS`, valor operacional ~2h) ou reduzir
   temporariamente esse valor no ambiente de teste, rodar o cleanup de novo — esperado: os
   arquivos são removidos pelo caminho de TTL de segurança.

## 7. Regressão — legado `.mp3` não quebra o pipeline

Criar manualmente um diretório de chamada com apenas `tx.mp3`/`rx.mp3` (sem `.raw`/`.wav`) dentro
de `RECORDINGS_PATH` e rodar o ciclo de backup SMB (passo 4) apontando para esse diretório
sintético. Esperado: o ciclo trata como par incompleto (`status: "pending", reason:
"mono_pair_incomplete"`), sem exceção e sem publicar arquivo corrompido.

## 8. Validar que o `smb_sync` ignora uma chamada em andamento (D-14)

Esta é a verificação direta do bug encontrado em `/brainstorming-multiagent`
(`investigation.md#6`) — confirma que a correção realmente fecha a corrida, não só que o
comportamento final parece certo.

1. Originar uma chamada real e mantê-la ativa (não desligar ainda).
2. Enquanto `tx.tmp.raw`/`rx.tmp.raw` estão crescendo (confirmado no passo 2), disparar o ciclo
   de backup SMB manualmente (comando do passo 4), apontando para o diretório de gravações
   inteiro (não só para essa chamada).
3. Esperado: o ciclo **não** toca no diretório dessa chamada — nem converte, nem publica, nem
   marca como consumida. `smb_transfer_log.json` não deve ganhar entrada para esse `call_id`
   nesse ciclo.
4. Encerrar a chamada normalmente e confirmar que ela segue o fluxo normal dos passos 3-5 depois
   disso.

## 9. Validar capacidade de 2 GiB e 30 chamadas

1. Confirmar que o mount `zenith_recordings_tmpfs` reporta aproximadamente 2 GiB.
2. Executar teste representativo com até 30 gravações simultâneas de até 5 minutos, sem usar
   containers ou volumes de outros projetos.
3. Observar ocupação durante captura, conversão e publicação SMB. Registrar o menor espaço livre.
4. Esperado: ocupação nunca ultrapassa 80%; nenhuma escrita falha; backlog SMB não cresce de forma
   sustentada. Resultado abaixo de 20% livre bloqueia o deploy — não autoriza alterar o tamanho
   novamente sem nova decisão.

## 10. Validar temporário órfão em duas rodadas

1. Em diretório sintético isolado, criar um `tx.tmp.raw` sem lease válido.
2. Rodar cleanup: esperado arquivo preservado e entrada em `.cleanup-candidates.json`.
3. Simular uma rodada completa (configuração de teste) e rodar novamente: esperado temporário
   removido sem criação de `tx.raw`/`tx.wav`.
4. Repetir criando/renovando `.capture-processing` entre as rodadas: esperado candidatura
   cancelada e temporário preservado.
5. Validar também `tx.tmp.wav` e `stereo.tmp.wav`; o remoto `<final>.wav.tmp` é validado pelo
   ciclo SMB, não pelo cleanup local.

## 11. Validar modo degradado de gravação

1. Em ambiente controlado, reduzir o espaço projetado disponível até que uma nova reserva deixe
   menos de 20% livre.
2. Originar uma nova chamada: esperado SIP normal, mas sem novo stream/arquivo de gravação; métrica
   de recusa e alerta crítico incrementados uma vez.
3. Confirmar que gravações anteriormente admitidas continuam crescendo.
4. Liberar espaço até 30% projetados e originar nova chamada: esperado retorno da gravação e
   transição observável de saída do modo degradado.

## 12. Rollout e rollback coordenados

1. Registrar revisões/imagens atuais dos serviços `zenith-*` afetados.
2. Inspecionar e drenar `zenith:audio-upload`; não apagar jobs ou gravações sem evidência.
3. Atualizar em uma janela coordenada API 1/2, uploader, SMB e cleanup. Não tocar em nenhum recurso
   sem prefixo `zenith-`.
4. Executar os passos 2 a 11 deste onboarding.
5. Em falha, restaurar conjuntamente as revisões anteriores dos serviços afetados e confirmar
   saúde SIP; não retomar a feature 013.

## 13. Checklist final

- [ ] `tx.wav`/`rx.wav` confirmados como PCM16 mono 16 kHz via `ffprobe`
- [ ] `tx.tmp.raw`/`rx.tmp.raw` crescem em disco durante a chamada (antes do hangup)
- [ ] Taxa efetiva confirmada por vazão (bytes/s), não só pelo rótulo do `.wav` final
- [ ] `stereo.wav` publicado no SMB, checksum conferido, reproduzível
- [ ] `.consumed-smb` criado após confirmação do backup
- [ ] Exclusão antecipada por confirmação observada (antes do TTL)
- [ ] Rede de segurança do TTL observada (sem confirmação)
- [ ] Diretório com `.mp3` legado ignorado sem erro
- [ ] `smb_sync` comprovadamente ignora uma chamada em andamento (passo 8)
- [ ] `zenith_recordings_tmpfs` confirmado em 2 GiB
- [ ] 30 chamadas de até 5 min mantêm ao menos 20% livre (passo 9)
- [ ] Temporário órfão descartado somente na segunda rodada; lease reaparecido cancela (passo 10)
- [ ] Modo degradado preserva SIP/ativas e usa histerese 20%/30% (passo 11)
- [ ] Rollout/rollback limitados a `zenith-*` e fila incompatível drenada (passo 12)
- [ ] `pytest -v tests src` verde
