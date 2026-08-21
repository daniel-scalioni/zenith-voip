# Investigation: Captura de áudio em WAV 16 kHz na origem

> Identificador: `014-captura-wav-16k`
> Data: `2026-08-12`
> Suporta as decisões técnicas do `roadmap.md`

## 1. Token de taxa do `uuid_audio_stream` (suporta D-01)

O `requirements.md` (seção 2) já registra a evidência primária, coletada por inspeção direta do
binário em produção (`10.10.10.11`, `fs_cli -x "uuid_audio_stream"` + `strings
mod_audio_stream.so`):

- O `usage` do módulo documenta os tokens de taxa como `[8000 | 16000]`, não `8k`/`16k`.
- O binário não contém nenhum literal `8k`/`16k`/`8000`/`16000` isolado além da própria string de
  `usage` — mas contém `"invalid sample rate: %s"`, evidência de que o parser é numérico e
  rejeitaria (ou cairia em default) para um token fora do formato esperado.
- O código atual (`stereo 8k`) funciona hoje, o que é consistente com "token não reconhecido →
  default 8000", não com "16k funcionaria por analogia".
- O módulo também expõe `"(%s) resampling from %u to %u"` / `"(%s) no resampling needed for this
  call"` — confirma que a reamostragem para a taxa pedida acontece dentro do FreeSWITCH antes de
  chegar ao WebSocket, sustentando RN-06 (16 kHz é formato-alvo, não promessa de largura de banda
  da fonte).

**Conclusão:** usar o token numérico `16000` é a única opção com evidência de contrato — não uma
escolha entre alternativas equivalentes. Por isso D-01 não lista alternativa descartada por
trade-off, lista a hipótese de manter `16k` por analogia, descartada por falta de contrato.

## 2. Conversão `.raw` → `.wav`: `ffmpeg` vs. `wave` (stdlib) (suporta D-02)

> **Correção (2026-08-13):** a versão original desta seção afirmava que `wave.writeframes()`
> "exige ler o payload PCM inteiro em memória do processo antes de escrever". Isso está errado —
> a revisão via `advisor()` mostrou que `wave.Wave_write.writeframesraw()` escreve
> incrementalmente (cada chamada grava só os bytes passados a ela) e só faz *seek* para corrigir
> os tamanhos do cabeçalho RIFF em `close()`, se o arquivo for seekable (confirmado lendo
> `Lib/wave.py` do CPython). A tabela abaixo foi corrigida; a conclusão (ffmpeg) não muda, mas
> por outro motivo.

| Critério | `ffmpeg` (subprocess, padrão já usado) | `wave` (stdlib Python) |
|---|---|---|
| Consistência com o código existente | `_convert_to_mp3` e `generate_stereo` já usam `ffmpeg` via `asyncio.create_subprocess_exec` — `generate_stereo` continua dependendo de `ffmpeg` de qualquer forma, para a mixagem estéreo | Introduziria um segundo mecanismo de conversão no mesmo domínio, sem eliminar a dependência de `ffmpeg` (que `generate_stereo` mantém) |
| Leitura/escrita do `.raw` → `.wav` | `ffmpeg` processa por streaming, fora do processo Python | Também suporta escrita incremental (`writeframesraw` por chunk, sem acumular em memória) — **não** é um problema de memória, ao contrário do que uma versão anterior desta análise concluiu |
| Fidelidade ao texto do requirements | RN-09/Gherkin descrevem "conversão para WAV" como uma etapa distinta, posterior à escrita incremental do `.raw` — uma conversão via subprocess separado é a leitura mais direta desse texto | Teria que ser adaptado para rodar como uma etapa de "reabrir o `.raw` e reescrever como `.wav`" já finalizado, funcionalmente equivalente, mas um padrão novo no código só para isso |
| Dependência nova | Nenhuma (`ffmpeg` já é dependência de imagem, usado por `generate_stereo`) | Nenhuma (stdlib) |

**Conclusão revisada:** `ffmpeg` continua sendo a escolha, mas por consistência com o único
mecanismo de conversão já usado no projeto (que `generate_stereo` não dispensa de qualquer
forma) — não porque a alternativa da stdlib tivesse um problema de memória real. Ver D-02.

## 3. Mecanismo de confirmação de consumo (suporta D-09/D-10/D-11/D-12)

RN-07/RF-08 pedem um mecanismo que hoje tem um único consumidor (SMB, feature `011`) mas precisa
acomodar um segundo (transcrição, feature `013`, hoje pausada) sem redesenho. Três formas
avaliadas:

1. **Marcador de arquivo por consumidor** (escolhida) — `.consumed-smb`, `.consumed-transcricao`,
   etc., escritos atomicamente no diretório da chamada quando cada consumidor termina. A checagem
   é "todos os marcadores da lista exigida existem?". Precedente direto no próprio código: o
   `.smb-processing` (lease) já é um arquivo de controle no mesmo diretório, com o mesmo padrão de
   escrita atômica (`write_lease`, `smb_sync.py:177-193`).
2. **Linha em `smb_transfer_log.json`** — reaproveitar o `state[key]["status"] == "done"` que já
   existe. Descartada como fonte única porque é um artefato interno do `smb_sync`, específico de
   um consumidor; a `013` teria de aprender a ler o formato do log do SMB para declarar seu
   próprio consumo, o que é acoplamento na direção errada (`013` dependeria de `011`).
3. **Coluna em `Call` (PostgreSQL)** — descartada por D-13: exige migração Alembic para um dado
   que só importa enquanto o arquivo existe em disco, e introduz uma dependência nova
   `workers → database` só para este propósito (o cleanup já opera puramente sobre filesystem
   hoje).

A opção 1 é a única que trata "consumidor" como um conceito de primeira classe, desacoplado tanto
do SMB quanto do banco — exatamente o "sem exigir redesenho" pedido pela RF-08.

## 4. Escrita incremental em disco: cadência de flush (suporta D-03)

RN-09 deixa a cadência de flush explicitamente como detalhe de plano. A opção considerada e
adotada é a mais simples: `write()` bufferizado padrão do Python (`open(path, "ab")`), sem
`flush()`/`fsync()` explícito por chunk.

- **A favor:** o objetivo declarado da RN-09 é limitar o crescimento de memória do processo
  proporcional à duração da chamada — um `io.BufferedWriter` já satisfaz isso, porque seu buffer
  interno é de tamanho fixo (poucos KB), não cresce com o tempo de chamada.
- **Contra fazer `fsync` por chunk:** os frames do `mod_audio_stream` chegam em alta frequência
  (dezenas de vezes por segundo, RTP-like); `fsync` síncrono nessa cadência introduziria I/O
  bloqueante no caminho do WebSocket, arriscando exatamente o jitter que o RNF de desempenho
  (rede/CPU) proíbe.
- **Durabilidade:** perder o conteúdo do buffer do SO em caso de crash do processo é uma
  degradação equivalente à que já existe hoje (buffer em RAM inteiro perdido em crash) — na
  prática esta mudança é estritamente mais resiliente que o comportamento atual, não menos.

## 5. Ordem entre `CHANNEL_HANGUP` (ESL) e desconexão do WebSocket (suporta D-04)

Não há evidência no legado de que essa ordem seja garantida — são dois transportes independentes
(socket ESL de eventos vs. WebSocket do `mod_audio_stream`). O código atual não precisa se
preocupar com isso porque o único efeito colateral do hangup é um `pop()` num dict em memória
(idempotente por natureza: um segundo `pop()` no mesmo `call_id` só devolve uma lista vazia). Ao
introduzir um recurso de sistema com estado real (arquivo aberto), essa suposição implícita deixa
de valer — por isso a decisão explícita em D-04.

## 6. Revisão via `advisor()` + `/brainstorming-multiagent`: corrida entre captura incremental e `smb_sync` (suporta D-14/D-15)

### 7.1 O achado do `advisor()`

Antes de fechar este roadmap, uma chamada a `advisor()` (revisor com o histórico completo da
sessão) identificou que a versão inicial de D-03 (escrever direto em `<channel>.raw` durante a
chamada) quebrava uma suposição implícita de `smb_sync._run_cycle`: esse worker varre
`RECORDINGS_PATH/*/*` a cada `SMB_SYNC_INTERVAL_MINUTES` (cron ARQ, independente de qualquer
evento de chamada) e `ensure_mono_pair` trata "`.raw` presente, `.wav` ausente" como "chamada
finalizada, aguardando conversão" — verdade sob a arquitetura antiga (`.raw` só existia
pós-hangup, escrito de uma vez pelo uploader), falsa sob RN-09 (`.raw` também existe *durante*
uma chamada ativa). Sem correção, uma chamada em andamento poderia ser convertida, publicada no
SMB, marcada como consumida e ter seu `.raw`/`.wav` apagado pelo `audio_cleanup` — enquanto o
`AudioIngestor` ainda escrevia nela. O mesmo `advisor()` também corrigiu uma alegação errada
sobre o módulo `wave` (ver `investigation.md#2`) e apontou o risco de capacidade do tmpfs
detalhado no `roadmap.md#9`.

### 7.2 A consulta multiagente

A correção inicialmente cogitada (marcador `.call-active` por diretório, escrito pelo
`AudioIngestor` e lido por `smb_sync`/`audio_cleanup`) foi submetida a três modelos reais, cada
um com uma lente diferente, via `/brainstorming-multiagent`, em sequência (nunca em paralelo):

| Modelo | CLI | Lente | Achado principal |
|---|---|---|---|
| Codex | `codex exec --sandbox read-only` | Arquitetura/acoplamento | O marcador é uma forma válida de coordenação, mas deveria virar um contrato explícito num módulo neutro (ex. `src/audio/recording_lifecycle.py`), não um nome de arquivo combinado por convenção implícita entre `audio` e `workers`. Levantou também uma suspeita sobre múltiplos handles por canal — não se aplica: há um único WebSocket por `call_id`, `tx`/`rx` vêm do de-interleaving do mesmo frame (`ingestor.py:51-57`) |
| Claude Opus (`--model opus`) | `claude --print --tools "Read,Grep,Glob"` | Profundidade técnica / risco não coberto | **Achado que invalidou o marcador:** sendo escrito uma única vez, o `mtime` do `.call-active` fica congelado; `audio_cleanup` apaga qualquer arquivo por `mtime < cutoff` que não esteja explicitamente protegido — uma chamada mais longa que a retenção perderia o marcador *no meio da chamada*, reabrindo o bug sem crash nenhum. Também identificou a janela exata perigosa (entre criar o marcador e escrever o primeiro `.raw`, não entre `makedirs` e o marcador) e sugeriu a correção estrutural adotada: nomear o artefato em progresso de forma diferente do nome final (`.tmp.raw` + rename), fechando a corrida por construção em vez de por coordenação |
| DeepSeek (`opencode/deepseek-v4-flash-free`) | `opencode run` | Pragmatismo/simplicidade | Comparou o marcador contra uma heurística por `mtime` (pular `.raw` "recente"); recomendou o marcador sobre a heurística de `mtime`, por esta reabrir o mesmo bug de outra forma (silêncio na fala/supressão de silêncio faz o `.raw` parecer "parado"). Não tinha visibilidade da alternativa de renomeação que a lente de profundidade técnica trouxe — se tivesse, a aritmética de simplicidade favorece ainda mais essa opção, por não exigir nenhum código novo em `smb_sync`/`audio_cleanup` |

### 7.3 Síntese e decisão

As três lentes convergem em rejeitar o `.raw` direto sem proteção, e divergem sobre *como*
proteger. A lente de profundidade técnica (Opus) encontrou o motivo mais forte para descartar o
marcador (mtime congelado sendo varrido pelo próprio cleanup) e, ao mesmo tempo, propôs a
alternativa que também resolve a objeção de arquitetura do Codex (nenhum contrato novo entre
domínios, porque não há mais marcador para interpretar) e é estritamente mais simples que a
proposta original que a lente de pragmatismo (DeepSeek) estava comparando. Por isso D-14 adota
a renomeação (`<channel>.tmp.raw` → `<channel>.raw` na finalização) em vez do marcador de
arquivo — nenhuma das três lentes avaliou essa opção diretamente (ela emergiu da resposta da
lente de profundidade técnica como um adendo à pergunta original), mas ela é estritamente
superior às duas que foram avaliadas frontalmente sob os critérios de cada uma. O risco (b) do
Opus (dois processos escrevendo a mesma chamada se a invariante de instância única falhar) não
tem correção proposta — é pré-existente ao `ESLClient` e está fora do escopo desta feature;
registrado em `roadmap.md#9` por transparência.

## 7. Revisão de temporários, capacidade e concorrência (2026-08-14)

Após a decisão `.tmp.raw`, uma busca transversal mostrou que `audio_cleanup.py` não opera por
nomes finais: percorre todo arquivo por `mtime` e protege somente `.smb-processing`. O roadmap
anterior dizia o oposto em D-14. Nova consulta sequencial via `/brainstorming-multiagent` usou:

| Modelo | CLI | Lente | Contribuição aceita |
|---|---|---|---|
| Claude Sonnet | Claude CLI | arquitetura/rastreabilidade | Identificou ausência de lease de captura, cleanup em duas rodadas, pressão runtime e mudança explícita para 2 GiB; destacou `_FFMPEG_INPUT_ARGS` ainda em 8 kHz |
| Gemini 3 Flash | Gemini CLI | capacidade/rollout | Confirmou insuficiência de 512 MB, necessidade de histerese/telemetria e rollout coordenado do payload ARQ |
| DeepSeek V4 Flash | OpenCode | races/crash | Identificou metadata perdida entre WS/hangup, jobs duplicados, cleanups concorrentes, falha de lease e órfão remoto |

O julgamento rejeitou três extrapolações: Gemini contou cada WAV mono como se tivesse o tamanho
do par e assumiu 30 mixagens SMB simultâneas, embora o loop seja sequencial; sua suspeita de
metadata entre réplicas não se aplica porque `AUDIO_STREAM_CALLBACK_HOST` aponta diretamente para
`fastapi-1`; DeepSeek tentou aplicar duas rodadas também a finais já consumidos, quando a decisão
humana se restringe a temporários órfãos. A síntese adotada está em D-16 a D-24.

## 8. Fontes consultadas

- `_reversa_sdd/domain.md` (R39-R43)
- `_reversa_sdd/code-analysis.md` (`#3-audio`, `#9-telephony`, `#10-workers`)
- `_reversa_sdd/addenda/011-smb-audio-backup.md`
- `_reversa_forward/013-transcricao-persistida/roadmap.md#D-04` (citado no requirements)
- Código-fonte: `src/telephony/esl_client.py`, `src/audio/ingestor.py`,
  `src/workers/audio_uploader.py`, `src/workers/smb_sync.py`, `src/workers/audio_cleanup.py`,
  `src/config.py`
- Inspeção de host de produção 2026-08-12 (citada no requirements, seção 2)
