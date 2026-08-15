# Interface: Arquivos de gravação de chamada (canal e estéreo)

> Identificador: `014-captura-wav-16k`
> Tipo de contrato: arquivo (filesystem)
> Data: `2026-08-12`
> Confidência: 🟢 CONFIRMADO

## 1. Propósito

Documenta o formato e o ciclo de vida dos arquivos de áudio que esta feature entrega, para que a
feature `013-transcricao-persistida` (pausada, dependente deste contrato) e qualquer consumidor
futuro não precisem ler o código-fonte de `src/audio/`, `src/telephony/` ou `src/workers/` para
saber o que esperar.

## 2. Contrato: arquivo de canal (`tx.<ext>` / `rx.<ext>`)

| Campo | Valor |
|---|---|
| Localização | `RECORDINGS_PATH/<tenant_id>/<call_id>/tx.wav` e `.../rx.wav` |
| Formato | WAV (RIFF), PCM16 (Pulse Code Modulation, 16 bits por amostra, sem compressão) |
| Canais | 1 (mono) — `tx` e `rx` sempre em arquivos separados, nunca misturados |
| Taxa de amostragem | 16000 Hz |
| Semântica do canal | `tx` = voz do atendente (pares no frame estéreo recebido do FreeSWITCH); `rx` = voz do cliente (ímpares) |
| Visibilidade | Só existe com este nome final após rename atômico. Durante a chamada, o canal existe como `<channel>.tmp.raw`; na finalização vira `<channel>.raw`; a conversão escreve `<channel>.tmp.wav` e publica `<channel>.wav`. Todo nome com `.tmp` é privado do produtor e invisível a consumidores |
| Garantia de degradação | Se a conversão para WAV falhar, `<channel>.raw` permanece em disco (`uploaded_raw_only`) — o áudio recebido nunca é perdido, só fica num formato intermediário |
| Fidelidade real | 16 kHz é o formato-alvo do pipeline (nativo do `whisper.cpp`), não uma garantia de conteúdo espectral acima de ~4 kHz — chamadas em codec narrowband (G.711, típico do tronco PSTN) chegam reamostradas pelo FreeSWITCH, não com informação nova |
| Ciclo de vida / exclusão | Removido assim que todos os consumidores exigidos confirmarem consumo (ver `data-delta.md#2.3`); nunca antes disso. Se nenhum consumidor confirmar, removido pelo TTL de segurança (`AUDIO_RETENTION_DAYS`) |

## 3. Contrato: arquivo estéreo publicado no SMB

| Campo | Valor |
|---|---|
| Origem local | Mixagem escreve `stereo.tmp.wav` e publica `stereo.wav` por rename atômico; o final local existe só durante a publicação e é removido após checksum remoto confirmado |
| Formato | WAV (RIFF), PCM16 |
| Canais | 2 (estéreo) — canal esquerdo = `tx`, canal direito = `rx` (`amerge`, mesma convenção de posição já usada no MP3 anterior) |
| Taxa de amostragem | 16000 Hz |
| Destino remoto | Compartilhamento SMB, diretório `{tenant}/{YYYY-MM-DD}`, nome `{timestamp}-{call_id[0:6]}-{origem}-{destino}.wav` (`build_remote_name`, extensão agora parametrizada) |
| Integridade | Upload remoto escreve `<final>.wav.tmp`; checksum SHA256 é conferido antes do rename remoto para `<final>.wav` e da remoção local |
| Consumidor humano | Equipe de Qualidade — abre o arquivo remoto para escuta; nenhuma mudança de procedimento esperada além de o player reproduzir WAV em vez de MP3 |

## 4. O que NÃO faz parte deste contrato

- O `.md` de transcrição da feature `013` tem extensão e formato próprios, decididos
  independentemente por aquela feature (RN-08 do `requirements.md`).
- Nenhum consumidor deve assumir `.mp3` implicitamente após esta feature — um diretório de chamada
  só com arquivos `.mp3` (formato anterior) é tratado como par incompleto/pendente, nunca como
  erro (RF-04).

## 5. Erros esperados por quem consome este contrato

| Cenário | Comportamento esperado |
|---|---|
| `tx.wav`/`rx.wav` ainda não existem (chamada em andamento ou aguardando conversão) | Consumidor deve tratar como "ainda não disponível", não como erro — mesmo padrão hoje aplicado pelo backup SMB (`status: pending`, `reason: mono_pair_incomplete`) |
| Diretório contém `tx.tmp.raw`/`rx.tmp.raw` (chamada em andamento) | Nome transitório — nenhum consumidor externo deve ler, converter ou publicar a partir dele. Ele nunca deve ser interpretado como "pronto para processar"; se algum consumidor futuro glob'ar por `*.raw` em vez de checar o nome exato, esse é o erro a evitar |
| Diretório contém `tx.tmp.wav`/`rx.tmp.wav` ou `stereo.tmp.wav` | Conversão/mixagem incompleta — ignorar; somente o produtor do estágio pode substituir ou descartar o temporário |
| Temporário local permanece sem lease válido após crash | Cleanup registra candidato na primeira rodada e descarta na segunda se identidade e ausência de lease permanecerem; nunca promove o conteúdo |
| Temporário remoto `<final>.wav.tmp` permanece após crash | O worker SMB registra e remove o órfão numa observação posterior; o cleanup local não acessa o compartilhamento remoto |
| Diretório com apenas `.mp3` legado, sem `.raw`/`.wav` | Tratado como par incompleto — nunca produz exceção nem publica arquivo corrompido |
| Falha na conversão `.raw` → `.wav` | `.raw` permanece em disco; falha fica registrada em log estruturado identificável por `call_id` (não em `print()`) |

## 6. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-12 | Versão inicial gerada por `/reversa-plan`, RF-07 | reversa |
| 2026-08-13 | Nome transitório do canal durante a chamada corrigido de `.raw` para `.tmp.raw` (D-14, achado de `/brainstorming-multiagent`) | reversa |
| 2026-08-14 | Protocolo completo de `.tmp.raw`/`.tmp.wav`/`stereo.tmp.wav`/remoto `.wav.tmp`, leases e descarte de órfãos em duas rodadas incorporado | reversa |
