# Requirements: Captura de áudio em WAV 16 kHz na origem

> Identificador: `014-captura-wav-16k`
> Data: `2026-08-12`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Troca o formato nativo de gravação das chamadas: em vez de MP3 mono 8 kHz por canal
(`tx.mp3`/`rx.mp3`), o pipeline passa a produzir WAV PCM16 mono **16 kHz** (`tx.wav`/`rx.wav`),
elevando também a taxa de captura pedida ao FreeSWITCH para o argumento literal
`uuid_audio_stream ... stereo 16000`. O MP3 8 kHz foi uma escolha arbitrária do primeiro corte e
é lossy; 16 kHz mono PCM é o
formato de entrada nativo do `whisper.cpp`, motor já decidido para a feature
`013-transcricao-persistida`, que depende desta. A feature entrega o novo formato ponta a ponta e
adapta os consumidores existentes (backup SMB da feature `011`), sem introduzir transcode
intermediário no caminho da transcrição.

**Escopo ampliado em `/reversa-clarify` (2026-08-12):** as três dúvidas abertas na versão inicial
tiveram respostas que alargam a feature além da simples troca de extensão — passam a fazer parte
do escopo (a) uma política de retenção por confirmação de consumo, não só TTL; (b) o arquivo
estéreo publicado no SMB também migra de MP3 para WAV; e (c) a captura deixa de acumular o áudio
inteiro da chamada em memória, escrevendo em disco de forma incremental. Ver seção 9 para o
racional completo de cada decisão.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/domain.md#R42` | "Captura é disparada pela **aplicação via ESL** (Event Socket Layer, a interface de comandos e eventos do FreeSWITCH) no CHANNEL_ANSWER, não pelo dialplan" (`esl_client.py:224-238`) — o parâmetro de taxa vive no comando `uuid_audio_stream {call_id} start {ws_url} stereo 8k` (`src/telephony/esl_client.py:256`), não em XML de dialplan. O comentário em `src/workers/audio_uploader.py:7-8` aponta para `freeswitch/conf/dialplan/default.xml` e está **desatualizado** | 🟢 |
| `_reversa_sdd/domain.md#R39` | "Cada canal vira um **MP3 mono 8 kHz** separado (`tx.mp3`, `rx.mp3`) — nunca misturado" (`audio_uploader.py:11,25-33`) — regra 🟢 que esta feature altera diretamente | 🟢 |
| `_reversa_sdd/domain.md#R41` | "Layout de gravação: `RECORDINGS_PATH/<tenant_id>/<call_id>/<channel>.mp3`" — a extensão muda, o layout de diretórios não | 🟢 |
| `_reversa_sdd/domain.md#R40` | "Falha de conversão preserva o `.raw` (`uploaded_raw_only`) — degrada, não perde" — garantia que precisa sobreviver à mudança de formato | 🟢 |
| `_reversa_sdd/domain.md#R43` | "Frame estéreo é dividido por índice: pares = `tx` (agente), ímpares = `rx` (cliente)" (`ingestor.py:86-94`) — o de-interleaving é agnóstico à taxa de amostragem, continua válido em 16 kHz | 🟢 |
| `_reversa_sdd/code-analysis.md#3-audio` | `AudioIngestor` acumula os chunks **em memória** (`self.buffers[call_id]`) durante toda a chamada; o disco só é tocado no hangup (`esl_client.py:277-286` → `enqueue_recording_upload`). Dobrar a taxa de amostragem dobra esse consumo de RAM por chamada ativa | 🟢 |
| `_reversa_sdd/addenda/011-smb-audio-backup.md#Impactos que devem permanecer visíveis` | "`tx.mp3` e `rx.mp3` continuam sendo as fontes mono; o estéreo é derivado e transitório localmente" — impacto declarado vigente da feature `011` que esta feature altera de forma consciente (`ensure_mono_pair`/`generate_stereo`, `src/workers/smb_sync.py:438-496`) | 🟢 |
| `_reversa_forward/013-transcricao-persistida/roadmap.md#D-04` | O chunking previsto para a transcrição alimenta o `WhisperCppSTT`; com fonte MP3 8 kHz seria necessário reamostrar para 16 kHz dentro do worker de STT. Esta feature remove essa etapa na origem — decisão do usuário em 2026-08-12 | 🟢 |
| Host de produção `10.10.10.11`, inspeção de 2026-08-12 (`fs_cli -x "uuid_audio_stream"`) | O `usage` do módulo declara os tokens de taxa como **`[8000 \| 16000]`**, não `8k`/`16k`. O binário `mod_audio_stream.so` não contém nenhum literal `8k`, `16k`, `8000` ou `16000` isolado — só a string de usage —, mas contém `"invalid sample rate: %s"`, indicando parse numérico do argumento. O código do projeto passa `stereo 8k` (`esl_client.py:256`), token fora do contrato documentado; a captura funciona hoje, o que sugere que o valor não reconhecido resulta no default de 8000 | 🟢 |
| Host de produção `10.10.10.11`, `strings mod_audio_stream.so` | O módulo contém `"(%s) resampling from %u to %u"` e `"(%s) no resampling needed for this call"` — a reamostragem para a taxa pedida acontece **dentro do FreeSWITCH**, confirmando RN-06 (16 kHz é formato-alvo, não ganho de banda) | 🟢 |
| Host de produção `10.10.10.11`, `df -h` e `find` em `/data/recordings` (2026-08-12) | O tmpfs de gravações está com **0% de ocupação e nenhum arquivo** (apenas a árvore de diretórios do tenant `akom`). Gravações não sobrevivem à recriação do container — não há acervo em `.mp3` a migrar no corte | 🟢 |
| `_reversa_sdd/telephony/design.md#GAP-PERF-01` | "Sem teste de carga do B2BUA" — lacuna aberta; esta feature aumenta o custo por chamada (RAM, disco, banda WebSocket) e não deve piorar esse quadro sem medição | 🔴 |
| `docker-compose.app.yml` (volume `zenith_recordings_tmpfs`) | Gravações vivem em **tmpfs de 512 MB** (RAM), com retenção `AUDIO_RETENTION_DAYS=0.0833` (≈ 2 h). WAV PCM16 16 kHz consome ~230 MB por hora-chamada (dois canais), contra estimadas ~29 MB/h no MP3 atual | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|----------------|
| Pipeline de transcrição (consumidor técnico, feature `013`) | Receber áudio no formato nativo do motor de STT (Speech-to-Text, conversão de fala em texto) | O worker de transcrição lê `tx.wav`/`rx.wav` e alimenta o `whisper.cpp` diretamente, sem etapa de reamostragem própria |
| Equipe de Qualidade (analista) | Ouvir a chamada gravada | Continua abrindo o arquivo publicado no SMB, com qualidade igual ou melhor que a atual — nenhuma mudança de procedimento |
| Operação / Infraestrutura | Manter o host de produção estável | Absorve o novo custo por chamada (RAM do buffer, ocupação do tmpfs, banda do WebSocket) sem degradar chamadas em andamento |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** A captura pede ao FreeSWITCH áudio estéreo a **16 kHz**, usando o token numérico
   documentado pelo módulo (`uuid_audio_stream {call_id} start {ws_url} stereo 16000`), não o
   sufixo `16k`. O código atual passa `8k`, token fora do contrato declarado no `usage` do
   módulo — provável motivo de a taxa efetiva coincidir com o default. 🟢
   - Origem no legado: `_reversa_sdd/domain.md#R42` (a captura é disparada via ESL, é ali que o
     parâmetro vive)
   - Tipo: alterada
2. **RN-02:** Cada canal passa a ser persistido como **WAV PCM16 mono 16 kHz** (`tx.wav`,
   `rx.wav`) — PCM (Pulse Code Modulation) de 16 bits por amostra, sem compressão com perda —,
   com header WAV válido, em vez de MP3 mono 8 kHz — nunca misturado, mantendo a
   separação física por canal. 🟢
   - Origem no legado: `_reversa_sdd/domain.md#R39` (regra 🟢 alterada por esta feature)
   - Tipo: alterada
3. **RN-03:** O layout de diretórios de gravação não muda
   (`RECORDINGS_PATH/<tenant_id>/<call_id>/<channel>.<ext>`); muda apenas a extensão do arquivo de
   canal. 🟢
   - Origem no legado: `_reversa_sdd/domain.md#R41`
   - Tipo: alterada (apenas na extensão)
4. **RN-04:** A garantia de "degrada, não perde" permanece: se a materialização do WAV falhar, o
   `.raw` recebido continua preservado em disco (`uploaded_raw_only`). 🟢
   - Origem no legado: `_reversa_sdd/domain.md#R40`
   - Tipo: nova aplicação de regra já confirmada
5. **RN-05:** Um arquivo de canal só é visível aos consumidores (backup SMB, transcrição) em seu
   nome final, após rename atômico — enquanto a chamada está ativa, existe exclusivamente como
   `<channel>.tmp.raw`; na finalização, vira `<channel>.raw` e só então é materializado como
   `<channel>.wav`. 🟢
   - Origem no legado: `_reversa_forward/011-smb-audio-backup/requirements.md#RF-09`, reafirmado
     em `_reversa_forward/013-transcricao-persistida/roadmap.md#D-09`
   - Tipo: nova aplicação de regra já confirmada
6. **RN-06:** 16 kHz é o **formato-alvo**, não uma promessa de banda de áudio: se a chamada
   trafega em codec narrowband (G.711, o caso típico do tronco PSTN), o FreeSWITCH entrega o sinal
   reamostrado, sem conteúdo espectral acima de ~4 kHz. O ganho real desta feature é eliminar a
   perda do MP3 e o transcode extra no caminho do STT, não elevar a fidelidade da fonte. 🟡
   - Tipo: nova (esclarecimento de expectativa)
7. **RN-07:** Um par `tx.wav`/`rx.wav` só é elegível para exclusão quando **todos** os consumidores
   registrados confirmarem consumo, não apenas por decurso de TTL. No corte desta feature, o único
   consumidor registrado é o backup SMB (`011`); a transcrição (`013`, hoje pausada) se registra
   como segundo consumidor exigido quando for mergeada, sem exigir redesenho do mecanismo. Um TTL
   de segurança (valor a definir em `/reversa-plan`) continua existindo como rede de proteção —
   nunca é aceitável reter gravação indefinidamente por um consumidor que nunca confirma. 🟢
   - Tipo: nova
   - Resolvida em `/reversa-clarify`, ver seção 9 (dúvida 1)
8. **RN-08:** O arquivo estéreo publicado no SMB (hoje `stereo.mp3`, derivado e transitório
   localmente) passa a ser **WAV estéreo 16 kHz**, não mais MP3 — prioriza fidelidade sobre
   tamanho de transferência. `build_remote_name` (`src/workers/smb_sync.py:117`) deixa de fixar
   `.mp3` e passa a aceitar a extensão como parâmetro; essa alteração pertence a esta feature, não
   à `013` (que segue livre para escolher a extensão do `.md` de transcrição
   independentemente). 🟢
   - Tipo: alterada
   - Origem no legado: `_reversa_sdd/addenda/011-smb-audio-backup.md#Impactos que devem
     permanecer visíveis` ("o estéreo é derivado e transitório localmente")
   - Resolvida em `/reversa-clarify`, ver seção 9 (dúvida 2)
9. **RN-09:** A captura deixa de acumular o áudio completo da chamada em memória do processo
   (`AudioIngestor.buffers`); cada chunk recebido é gravado incrementalmente no
   `<channel>.tmp.raw` em disco à medida que chega. A finalização faz o rename atômico para
   `<channel>.raw` antes da conversão para WAV (RN-05), processando o arquivo já em disco em vez de
   bytes acumulados em RAM ou payload de fila. 🟢
   - Tipo: alterada
   - Origem no legado: `_reversa_sdd/code-analysis.md#3-audio` (mecanismo de buffer em RAM que
     esta regra substitui)
   - Resolvida em `/reversa-clarify`, ver seção 9 (dúvida 3)

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|---------------------|-------------|
| RF-01 | Elevar a taxa pedida no comando `uuid_audio_stream` de `8k` para `16000` (`src/telephony/esl_client.py:256`), usando o token numérico do contrato do módulo, mantendo o modo `stereo` e o de-interleaving por índice já validado (RN-01, `domain.md#R43`). | Must | Numa chamada real, cada canal mono PCM16 cresce a aproximadamente 32.000 bytes/s; o comando não é rejeitado nem registra `invalid sample rate`; e `tx`/`rx` separados continuam contendo as vozes corretas (atendente/cliente), sem troca de canal. | 🟢 |
| RF-02 | Persistir cada canal como WAV PCM16 mono 16 kHz (`tx.wav`/`rx.wav`) com header válido, substituindo a conversão para MP3 em `audio_uploader._convert_to_mp3`, preservando o rename atômico (RN-05) e a preservação do `.raw` em caso de falha (RN-04). | Must | Após uma chamada real, `tx.wav` e `rx.wav` existem no diretório da chamada, abrem em qualquer player/`ffprobe` como PCM16 mono 16 kHz, e um arquivo em escrita nunca aparece com o nome final. | 🟢 |
| RF-03 | Adaptar **todos** os pontos da feature `011` que assumem `.mp3`: `ensure_mono_pair` (resolução do par, `smb_sync.py:438-450`), `generate_stereo` (mescla das fontes, agora produzindo **WAV estéreo** conforme RN-08, `smb_sync.py:453-496`), `build_remote_name` (`smb_sync.py:117`, deixa de fixar `.mp3` e passa a aceitar extensão), o nome da função de conversão `_convert_to_mp3` (`audio_uploader.py:14`, chamada de `ensure_mono_pair`) e os campos `tx_path`/`rx_path`/`stereo_path` gravados no log de transferência (`smb_sync.py:646-648`), que hoje montam o nome com `.mp3` fixo e passariam a registrar metadado errado em silêncio. | Must | O ciclo de backup SMB conclui normalmente para uma chamada real gravada no novo formato, com o arquivo estéreo publicado no SMB como WAV, íntegro (checksum) e reproduzível; o log de transferência aponta para caminhos que existem em disco; e não há regressão nos testes de `src/workers/test_smb_sync.py`. | 🟢 |
| RF-04 | Confirmar que o corte de formato não deixa acervo órfão: as gravações vivem em tmpfs (memória), que a inspeção de 2026-08-12 mostrou vazio e que é recriado a cada recriação de container — logo, não há `.mp3` legado a suportar. Caso a confirmação falhe no momento do deploy, os consumidores devem ignorar diretórios em formato antigo sem erro, em vez de suportá-los. | Should | No deploy, `/data/recordings` está vazio ou contém apenas diretórios sem par completo; se houver par `.mp3` remanescente, o ciclo de backup o ignora sem exceção e sem publicar arquivo corrompido. | 🟢 |
| RF-05 | Substituir a exclusão puramente por TTL por exclusão condicionada à confirmação de consumo (RN-07), com o TTL atual (`AUDIO_RETENTION_DAYS`) mantido como rede de segurança, não como gatilho primário. WAV PCM16 16 kHz ocupa ~230 MB por hora-chamada (dois canais) contra ~29 MB/h estimados no formato atual — a janela de retenção sozinha não é mais a única defesa contra estourar o tmpfs. Se a medição representativa indicar menos de 20% de espaço livre no pico, o tamanho do `zenith_recordings_tmpfs` deve ser aumentado antes do deploy. | Must | No pior caso operacional representativo, o pico ocupa no máximo 80% do `zenith_recordings_tmpfs`; uma chamada de teste tem seu `tx.wav`/`rx.wav` removidos assim que o backup SMB confirma consumo (sem esperar o TTL); e o TTL de segurança ainda remove gravações órfãs cujo consumidor nunca confirmou. Deploy bloqueado enquanto a margem livre medida for inferior a 20%. | 🟢 |
| RF-06 | Manter a suíte existente verde após a mudança de formato, incluindo os testes de `011` que assumem `.mp3` (`src/workers/test_smb_sync.py`, `src/workers/test_audio_uploader.py`), atualizados para o novo contrato. | Must | `pytest -v tests src` passa sem falhas, e os testes que codificavam `.mp3`/8 kHz passam a codificar o novo formato explicitamente (não apenas removidos). | 🟢 |
| RF-07 | Registrar o novo formato como contrato explícito para os consumidores seguintes (feature `013` e posteriores): extensão, taxa, profundidade, canais e localização — do arquivo de canal (`tx.wav`/`rx.wav`) e do arquivo estéreo publicado no SMB (RN-08). | Should | Existe um arquivo de interface na pasta da feature descrevendo os dois contratos, referenciável pela `013` sem precisar ler o código. | 🟢 |
| RF-08 | Implementar o mecanismo de confirmação de consumo que sustenta RF-05/RN-07: um par `tx.wav`/`rx.wav` só é candidato à exclusão quando os consumidores registrados (inicialmente só o backup SMB) confirmarem consumo; consumidores futuros (`013`) se registram sem exigir redesenho. | Must | Um teste simulando a confirmação do backup SMB remove o par correspondente antes do TTL expirar; um teste sem nenhuma confirmação preserva o par até o TTL de segurança agir. | 🟢 |
| RF-09 | Escrever os chunks de áudio recebidos diretamente em disco à medida que chegam (streaming append no `<channel>.tmp.raw`, RN-09), eliminando o acúmulo do áudio completo da chamada em memória do processo FastAPI; a finalização faz rename atômico para `<channel>.raw` antes da conversão para WAV. | Must | Numa chamada real de duração significativa, o consumo de RAM do processo `fastapi-*` não cresce proporcionalmente à duração da chamada; o `<channel>.tmp.raw` existe e cresce em disco durante a chamada; e nenhum `.raw` final fica visível antes da finalização. | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|------------------------------|-------------|
| Desempenho (memória) | RN-09 substitui o buffer em RAM por escrita incremental em disco — o consumo de memória do processo FastAPI por chamada ativa deixa de crescer com a duração da chamada. A cadência de flush por chunk (a cada frame recebido vs. em lote) é detalhe a decidir em `/reversa-plan`, mas o compromisso de não acumular a chamada inteira em RAM é `Must`. | `src/audio/ingestor.py:56` (mecanismo substituído), `src/telephony/esl_client.py:277-286`; host de produção com 15 GiB de RAM total e ~11 GiB disponíveis (coleta de 2026-08-12) | 🟢 |
| Desempenho (rede/CPU) | Dobrar a taxa dobra o tráfego do WebSocket de áudio e o volume de bytes processados no de-interleaving por chamada. Não pode introduzir jitter perceptível nas chamadas em andamento. | Relacionado a `_reversa_sdd/telephony/design.md#GAP-PERF-01` (carga do B2BUA nunca medida) | 🟡 |
| Capacidade | Ocupação do `zenith_recordings_tmpfs` cresce ~8x por hora-chamada. A exclusão por confirmação de consumo (RN-07/RF-08) é a defesa primária; o TTL (`AUDIO_RETENTION_DAYS`) permanece como rede de segurança. O pico do pior caso operacional representativo deve deixar ao menos 20% do volume livre; se os 512 MB atuais não atenderem, aumentar o tmpfs antes do deploy. Estourar o volume causa perda de áudio, não degradação. | `docker-compose.app.yml`, volume `zenith_recordings_tmpfs`; decisão da sessão de esclarecimento de 2026-08-13 | 🟢 |
| Rede (SMB) | O arquivo estéreo publicado no SMB passa de MP3 comprimido para WAV não comprimido (RN-08) — várias vezes maior por chamada. O throttle já existente (`SMB_BANDWIDTH_LIMIT_MBS`) evita saturar o link, mas o tempo de publicação por chamada cresce; não deve fazer a fila `zenith:smb-sync` acumular de forma sustentada. | `src/config.py#SMB_BANDWIDTH_LIMIT_MBS`, `src/workers/smb_sync.py::BandwidthLimiter` | 🟡 |
| Compatibilidade | A mudança é observável por qualquer consumidor do diretório de gravações; nenhum consumidor pode assumir `.mp3` implicitamente após esta feature. | `_reversa_sdd/addenda/011-smb-audio-backup.md#Impactos que devem permanecer visíveis` | 🟢 |
| Observabilidade | Falha de materialização do WAV, confirmações de consumo pendentes e ocupação do volume de gravações devem ser observáveis por log estruturado/métrica, nunca `print()`. | `AGENTS.md#Anti-Padrões`; padrão já existente em `src/utils/telemetry.py` (`set_smb_queue_size`) | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Chamada real grava os dois canais em WAV 16 kHz
  Dado que o FreeSWITCH está capturando áudio via uuid_audio_stream com o argumento 16000
  Quando uma chamada real é atendida e encerrada
  Então tx.wav e rx.wav existem no diretório da chamada
  E ffprobe identifica ambos como PCM16 mono 16000 Hz
  E o canal tx contém a voz do atendente e o rx a do cliente

Cenário: Backup SMB continua funcionando com o novo formato
  Dado que uma chamada foi gravada em tx.wav/rx.wav
  Quando o ciclo de backup SMB é executado para essa chamada
  Então o arquivo estéreo é publicado no SMB em WAV, com checksum conferido
  E o arquivo remoto é reproduzível pela equipe de Qualidade

Cenário: Gravação é removida assim que os consumidores confirmam consumo
  Dado que o backup SMB de uma chamada foi concluído com sucesso
  Quando o ciclo de limpeza avalia essa chamada, antes do TTL expirar
  Então tx.wav e rx.wav dessa chamada são removidos do tmpfs

Cenário: Gravação sem confirmação de consumo é preservada até o TTL de segurança
  Dado que o backup SMB de uma chamada ainda não confirmou consumo
  Quando o ciclo de limpeza avalia essa chamada, antes do TTL expirar
  Então tx.wav e rx.wav dessa chamada permanecem no tmpfs
  E só são removidos quando o TTL de segurança expirar

Cenário: Captura não acumula a chamada inteira em memória
  Dado uma chamada real de longa duração em andamento
  Quando chunks de áudio chegam continuamente pelo WebSocket
  Então cada chunk é escrito no <channel>.tmp.raw em disco à medida que chega
  E o consumo de memória do processo não cresce proporcionalmente à duração da chamada
  E nenhum .raw final fica visível antes da finalização

Cenário: Gravação antiga em MP3 não quebra o pipeline no corte de formato
  Dado que existe um diretório de chamada gravado no formato antigo (tx.mp3/rx.mp3)
  Quando o ciclo de backup SMB varre o diretório de gravações
  Então essa chamada é tratada sem erro e sem publicar arquivo corrompido
  E as chamadas novas em .wav seguem sendo processadas normalmente

Cenário: Falha na materialização do WAV não perde o áudio capturado
  Dado que a conversão do .raw para .wav falha
  Quando o job de persistência da gravação termina
  Então o arquivo .raw permanece em disco com o áudio recebido
  E a falha é registrada em log estruturado identificável por call_id

Cenário: Volume de gravações não estoura dentro da janela de retenção
  Dado o pior caso previsto de chamadas simultâneas gravando em WAV 16 kHz
  Quando o pico de ocupação do tmpfs é medido numa duração representativa
  Então o volume de gravações permanece em no máximo 80% de ocupação
  E nenhuma gravação falha por falta de espaço
  E o deploy é bloqueado até aumentar o tmpfs se a margem livre for inferior a 20%
```

> RF-06 (suíte verde) e RF-07 (documento de contrato) não têm cenário Gherkin por não descreverem
> comportamento observável do sistema em execução — são gates de processo, verificados pelo
> próprio quality gate do projeto e pela existência do artefato.

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|-----------------|
| RF-01, RF-02 | Must | São a feature: sem eles não existe captura nem persistência no novo formato |
| RF-03 | Must | Sem adaptar os consumidores da `011`, a mudança de formato quebra o backup SMB, que hoje é a entrega de valor em produção |
| RF-04 | Should | Rebaixado de Must após a inspeção do host: o tmpfs de gravações está vazio e é recriado no deploy, então não há acervo `.mp3` a suportar — resta confirmar a premissa no corte |
| RF-05 | Must | O tmpfs atual não comporta o novo custo com folga; estourar significa perder gravação, não degradar |
| RF-06 | Must | Gate de qualidade já estabelecido no projeto (`AGENTS.md#Quality Gates`) |
| RF-07 | Should | Facilita a retomada da `013`, mas a feature entrega valor sem o documento de interface |
| RF-08 | Must | Sem o mecanismo de confirmação, RF-05 não tem como funcionar — o tmpfs de 512 MB não sobrevive só com TTL de 2h no novo custo por chamada |
| RF-09 | Must | Sem escrita incremental, o novo custo de RAM por chamada ativa (RN-09) fica sem mitigação nesta feature, mesma decisão do usuário que motivou a dúvida 3 |
| RNF de desempenho (memória/rede) | Should | Precisa ser conhecido e registrado; virar bloqueio só se a medição indicar risco real ao B2BUA |
| RNF de rede (SMB) | Should | Publicar WAV é decisão tomada (RN-08), mas o impacto na fila de sincronização precisa ser observado, não necessariamente resolvido nesta feature |

## 9. Esclarecimentos

### Sessão 2026-08-12

- **Q:** Capacidade do armazenamento local (RF-05) — o `zenith_recordings_tmpfs` tem 512 MB em RAM
  e a retenção é de ≈ 2 h; a 16 kHz isso comporta apenas ~2,2 horas-chamada acumuladas. Qual
  caminho: (a) aumentar o tmpfs, (b) encurtar a retenção, (c) apagar o `.wav` assim que os
  consumidores confirmarem o consumo, ou (d) sair do tmpfs para disco?
  **R:** Opção (c) — apagar o `.wav` assim que os consumidores confirmarem o consumo. Vira RN-07
  (retenção por confirmação, com TTL como rede de segurança) e RF-08 (mecanismo de confirmação).
  RF-05 foi reescrito para refletir que a exclusão condicionada, não o TTL sozinho, é a defesa
  primária contra estourar o tmpfs.
- **Q:** Formato do arquivo publicado no SMB (RF-03) — continua MP3 (comprimido, para escuta
  humana) ou passa a ser WAV estéreo (fiel, porém maior)? A resposta também decide se a alteração
  de `build_remote_name` (que hoje fixa `.mp3`) pertence a esta feature ou à `013`.
  **R:** WAV estéreo. Vira RN-08; `build_remote_name` (`smb_sync.py:117`) passa a aceitar
  extensão como parâmetro e essa mudança é desta feature — a `013` segue livre para escolher a
  extensão do `.md` de transcrição de forma independente. RF-03 foi ampliado para cobrir
  `generate_stereo` produzindo WAV; uma nova linha de RNF (Rede/SMB) registra o impacto de
  transferir arquivos maiores.
- **Q:** Buffer em memória durante a chamada — aceitar o custo (com limite/alerta) ou ampliar o
  escopo para escrita incremental em disco durante a chamada?
  **R:** Ampliar o escopo. Vira RN-09 e RF-09: os chunks passam a ser gravados incrementalmente no
  `<channel>.tmp.raw` à medida que chegam, eliminando o acúmulo da chamada inteira em RAM. Na
  finalização, o transitório vira `<channel>.raw` por rename atômico antes da conversão WAV.

### Sessão 2026-08-13

- **Q:** Qual nome deve existir enquanto a chamada está ativa?
  **R:** `<channel>.tmp.raw`, invisível aos consumidores. Somente na finalização ele vira
  `<channel>.raw`, antes da materialização de `<channel>.wav`.
- **Q:** Se a medição indicar que o tmpfs de 512 MB não oferece margem segura, qual deve ser a
  regra?
  **R:** Aumentar o tmpfs antes do deploy. O gate exige ao menos 20% de espaço livre no pico do
  pior caso operacional representativo; margem inferior bloqueia a entrega.
- **Q:** Qual vazão deve constar no aceite de RF-01?
  **R:** Aproximadamente 32.000 bytes/s por canal PCM16 mono em 16 kHz. O requisito não usa uma
  baseline de 8 kHz, pois o formato antigo deixa de fazer parte do pipeline entregue.

## 10. Lacunas

Nenhuma lacuna aberta no momento. Todos os pontos levantados na versão inicial foram resolvidos
em `/reversa-clarify` (ver seção 9). `_reversa_sdd/telephony/design.md#GAP-PERF-01` (carga do
B2BUA nunca medida) permanece como lacuna aberta do legado, não desta feature — referenciado nos
RNFs de desempenho como contexto de risco, não como algo que esta feature precisa fechar.

## Pendências de Qualidade

Duas ressalvas conscientes da auto-validação (checklist `.reversa/templates/quality-template.md`),
mantidas por decisão de rastreabilidade:

- **Q-018 (não citar biblioteca/framework/produto):** o documento cita `uuid_audio_stream`,
  `ffprobe`, FreeSWITCH, MP3/WAV e nomes de arquivos do código. Sem essas âncoras, a feature
  perderia rastreabilidade com o legado — o formato de origem *é* o objeto da feature, e o comando
  ESL é onde o parâmetro fisicamente vive. Mesmo padrão já adotado nos requirements de `011` e
  `013`.
- **Q-010 (todo RF com cenário Gherkin):** RF-06 e RF-07 ficam sem cenário, pelo motivo registrado
  logo abaixo do bloco de critérios de aceitação.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-12 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-08-12 | Inspeção do host de produção incorporada: token de taxa do `mod_audio_stream` é `8000\|16000` (não `8k`/`16k`), reamostragem confirmada dentro do FreeSWITCH (RN-06), tmpfs de gravações vazio (RF-04 rebaixado a Should); RF-03 ampliado com os pontos `_convert_to_mp3` e log de transferência; acoplamento entre as dúvidas 1 e 3 e vínculo da dúvida 2 com `build_remote_name`/`013` registrados | reversa |
| 2026-08-12 | 3 dúvidas resolvidas via `/reversa-clarify` (retenção por confirmação de consumo, formato WAV do arquivo publicado no SMB, escrita incremental em disco durante a chamada); RN-07/RN-08/RN-09, RF-08/RF-09 adicionados; RF-03/RF-05/RF-07 e RNFs de desempenho/rede atualizados; escopo da feature ampliado além da troca de extensão original | reversa |
| 2026-08-13 | 3 inconsistências da auditoria resolvidas via `/reversa-clarify`: transitório padronizado como `<channel>.tmp.raw`, gate de capacidade fixado em 20% livre com aumento obrigatório do tmpfs antes do deploy e vazão de aceite corrigida para 32.000 bytes/s por canal PCM16 mono 16 kHz | reversa |
