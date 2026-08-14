# Roadmap: Captura de áudio em WAV 16 kHz na origem

> Identificador: `014-captura-wav-16k`
> Data: `2026-08-12`
> Requirements: `_reversa_forward/014-captura-wav-16k/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

A captura passa a pedir ao FreeSWITCH o token numérico `16000` em vez do sufixo `8k`
(`esl_client.py:256`). O `AudioIngestor` deixa de acumular `AudioChunk` em
`self.buffers[call_id]` e passa a manter um arquivo aberto por canal, gravando cada chunk
recebido do WebSocket diretamente em disco assim que chega — exatamente como RN-09/RF-09
descrevem (append incremental, conversão para WAV como etapa separada no hangup). A
finalização (fechar os handles, expor o `.raw` em seu nome estável, enfileirar a conversão) é
disparada de forma idempotente por dois gatilhos que competem — `CHANNEL_HANGUP` via ESL e o
encerramento do próprio WebSocket — porque nenhum dos dois tem ordem garantida sobre o outro;
quem chegar primeiro faz o trabalho, o segundo é no-op.

**Achado central, revisado via `/brainstorming-multiagent` (ver `investigation.md#6`):** tornar
`.raw` visível *durante* a chamada, e não só depois do hangup, quebra uma suposição implícita de
`smb_sync._run_cycle` — hoje ele varre `RECORDINGS_PATH/*/*` a cada `SMB_SYNC_INTERVAL_MINUTES`
e trata "`.raw` presente, `.wav` ausente" como "chamada finalizada, aguardando conversão". Sob
RN-09 isso deixa de ser verdade: uma chamada em andamento também bate nesse padrão. Sem
correção, o SMB sync converteria e publicaria um `.raw` truncado de uma chamada ainda ativa,
marcaria como consumido, e o cleanup apagaria a gravação real por baixo do handle ainda aberto
do `AudioIngestor`.

A primeira correção cogitada (marcador `.call-active` por diretório, no padrão do lease
`.smb-processing`) foi submetida a três lentes independentes (Codex — arquitetura/acoplamento;
Claude Opus — profundidade técnica; DeepSeek via OpenCode — pragmatismo). A revisão de
profundidade técnica achou uma falha que invalidava o marcador como estava proposto: sendo um
arquivo escrito uma única vez, seu `mtime` fica congelado, e o próprio `audio_cleanup` (que
apaga qualquer arquivo por `mtime < cutoff`, salvo os nomes explicitamente protegidos) o
apagaria no meio de uma chamada longa — reabrindo o bug original sem crash nenhum, só por
decurso de tempo. A correção adotada em seu lugar (D-14) é mais simples que o marcador e fecha a
janela por construção, não por coordenação: o canal é escrito em `<channel>.tmp.raw` durante a
chamada (mesmo idioma tmp+rename já usado três vezes no projeto) e só vira `<channel>.raw` — o
nome que `ensure_mono_pair` e todo o resto do pipeline reconhecem — no momento da finalização.
Enquanto a chamada está ativa, `.raw` simplesmente não existe; `smb_sync` e `audio_cleanup` não
precisam de nenhuma mudança para respeitar isso, porque nunca souberam procurar por
`.tmp.raw`. Detalhe completo da consulta em `investigation.md#6`.

O job ARQ de upload deixa de transportar bytes de áudio como payload de fila e passa a operar
sobre o `.raw` já em disco (só depois que a chamada é finalizada e renomeada), fechando o
segundo ponto de acúmulo em memória que a RN-09 elimina. `_convert_to_mp3` vira
`_convert_to_wav` (mesmo padrão de subprocess `ffmpeg`, agora `pcm_s16le`/16 kHz), reaproveitado
por `smb_sync.ensure_mono_pair`. `generate_stereo` produz `stereo.wav` (RN-08) e
`build_remote_name` deixa de fixar `.mp3`, recebendo a extensão como parâmetro. Um mecanismo
novo e pequeno (`recording_consumers.py`) grava um marcador atômico por consumidor confirmado
(`.consumed-<nome>`) no diretório da chamada — este marcador é pós-hangup, escrito só depois que
o par `.wav` já é estável, então não herda o problema de `mtime` congelado do (`.call-active`)
descartado: ele só precisa sobreviver até o cleanup rodar, não durante toda a duração de uma
chamada potencialmente longa. `audio_cleanup` remove `tx.wav`/`rx.wav` assim que todos os
consumidores exigidos (hoje só `smb`, configurável) confirmarem, mantendo o TTL por mtime já
existente como rede de segurança para quem nunca confirma. Nenhuma migração de banco é
necessária — todo o estado novo é arquivo, seguindo o precedente já em produção
(`.smb-processing`, `smb_transfer_log.json`).

Um segundo achado, também emergente da revisão — o pico de ocupação do tmpfs para uma única
chamada longa chega perto do teto de 512 MB mesmo sem concorrência nenhuma — não tem correção de
código; é um risco de capacidade explícito na seção 9, com aritmética concreta.

## 2. Princípios aplicados

`.reversa/principles.md` não tem conteúdo (nenhum princípio formal registrado ainda). Aplicam-se
os princípios já confirmados em `_reversa_sdd/architecture.md#Princípios-Arquiteturais` e as
regras transversais do `AGENTS.md`.

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| Processamento assíncrono (Redis Streams + Workers ARQ) | Conversão e backup continuam fora da cadeia crítica da chamada; o job de upload muda de payload, não de mecanismo | respeita |
| Isolamento de tenant | Layout `RECORDINGS_PATH/<tenant_id>/<call_id>/` não muda (RN-03) | respeita |
| Recursos Docker `zenith-*` | Nenhum novo container, volume ou rede — mesmo `zenith_recordings_tmpfs` | respeita |
| Anti-padrão "variável lida sem checar se foi definida" (`AGENTS.md`) | O gatilho duplo de finalização (hangup × WS disconnect) precisa ser idempotente por construção, não por sorte de ordem — ver D-04 | respeita (é o próprio objeto da decisão) |
| Spec-first e TDD | Este roadmap antecede `/reversa-to-do` e a implementação; RF-06 exige suíte verde antes de fechar | respeita |
| Observabilidade via log estruturado/métrica, nunca `print()` (`AGENTS.md#Anti-Padrões`) | Falha de materialização do WAV e confirmação pendente devem reaproveitar `src/utils/telemetry.py` | respeita |

Não há conflito de princípio identificado.

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | `_start_audio_capture` passa `stereo 16000` em vez de `stereo 8k` (`esl_client.py:256`) | RN-01; token numérico é o único documentado pelo `usage` do módulo (evidência de host, seção 2 do requirements) | Manter `16k` por analogia ao `8k` atual — descartada porque o `usage` do módulo não reconhece sufixo, só `[8000\|16000]` | 🟢 |
| D-02 | Conversão `.raw → .wav` reaproveita o padrão de subprocess `ffmpeg` já usado em `_convert_to_mp3`, trocando para `-c:a pcm_s16le` e mantendo `-ar 16000 -ac 1` | Mantém o único padrão de conversão do projeto — `generate_stereo` já depende de `ffmpeg` de qualquer forma; RN-09/Gherkin descrevem "conversão para WAV" como etapa distinta da escrita incremental, o que ffmpeg satisfaz diretamente | Módulo `wave` da stdlib — tecnicamente também suporta escrita incremental sem carregar o payload inteiro em RAM (correção de uma justificativa anterior desta mesma decisão, que estava errada nesse ponto); descartada por introduzir um segundo mecanismo de conversão no mesmo domínio quando `ffmpeg` já é a única dependência usada para isso, não por limitação de memória | 🟢 |
| D-03 | `AudioIngestor` mantém `raw_files: dict[call_id, dict[channel, BinaryIO]]`; abre `tx.tmp.raw`/`rx.tmp.raw` sob demanda no primeiro chunk daquele canal (`RECORDINGS_PATH/<tenant_id>/<call_id>/<channel>.tmp.raw`) e escreve cada chunk recebido do WebSocket imediatamente; `self.buffers` é removido | RN-09/RF-09 pedem escrita incremental sem acúmulo em RAM. O sufixo `.tmp.raw` (em vez de `.raw` direto) é o que fecha a corrida com `smb_sync` descrita no resumo — ver D-14. O `tenant_id` já está disponível em `stream_metadata` desde `register_stream_metadata` (CHANNEL_ANSWER) | Escrever direto em `<channel>.raw` desde o primeiro chunk (redação inicial desta decisão) — descartada depois da revisão multiagente por deixar `.raw` de uma chamada ativa indistinguível de um `.raw` de chamada finalizada aguardando conversão | 🟢 |
| D-04 | Finalização (fechar os dois handles `.tmp.raw` da chamada, `os.replace` para o nome final `.raw` por canal presente, enfileirar upload) é disparada por um método idempotente único, `AudioIngestor.finalize_call_recording(call_id)`, chamado de dois pontos: `_handle_channel_hangup` (ESL) e o `finally` de `handle_forked_stream` (desconexão do WebSocket). A idempotência vem de usar a própria remoção da entrada do dict como guarda — quem encontrar a entrada faz o trabalho e a remove; quem chegar depois encontra o dict vazio e não faz nada. Como há um único WebSocket por `call_id` (não um por canal — `tx`/`rx` vêm do de-interleaving do mesmo frame estéreo, `ingestor.py:51-57`), os dois canais fecham e renomeiam juntos, atomicamente, dentro da mesma chamada ao método | `CHANNEL_HANGUP` (evento ESL) e o fechamento do WebSocket do `mod_audio_stream` são duas fontes assíncronas independentes sem ordem garantida entre si — diferente do fluxo em RAM de hoje (onde o pop em `buffers` no hangup é a única leitura possível), aqui existe um recurso de sistema (arquivo aberto) que precisa ser fechado exatamente uma vez, por qualquer um dos dois gatilhos, sem depender de qual chega primeiro | Confiar apenas no hangup ESL para fechar os arquivos — descartada porque, se o WebSocket demorar a desconectar após o hangup (ou o hangup nunca chegar por falha de conexão ESL, já um caso conhecido de degradação em `esl_client.py`), os handles ficam abertos indefinidamente | 🟡 |
| D-05 | `enqueue_recording_upload(tenant_id, call_id)` deixa de receber `recordings: list[dict]` com bytes; `upload_recording_batch`/`upload_audio_chunk` passam a listar os `*.raw` já gravados (e já renomeados por D-04) em `RECORDINGS_PATH/<tenant_id>/<call_id>/` e convertê-los, um por canal encontrado | Fecha o segundo ponto de acúmulo em RAM citado pela RN-09 ("nem payload de fila") — hoje o payload do job ARQ carrega os bytes inteiros da chamada serializados via Redis | Manter bytes no payload do job, só mudando o formato de saída para WAV — descartada porque não resolve a memória citada em RN-09/RF-09, só troca o formato do arquivo final | 🟢 |
| D-06 | `ensure_mono_pair` procura `tx.wav`/`rx.wav` em vez de `tx.mp3`/`rx.mp3`; se nenhum dos dois existir (nem `.raw` pendente), retorna `None` como hoje — sem nenhum tratamento especial para `.tmp.raw`, que a função nunca chega a enxergar pelo nome | Mesmo comportamento de "pendente, sem exceção" que já existe para pares incompletos cobre RF-04 sem código novo: um diretório só com `.mp3` legado (sem `.raw`/`.wav`) simplesmente nunca completa o par e o ciclo de backup o ignora, como já faz hoje para qualquer par incompleto — e agora, pelo mesmo motivo, também ignora sem erro um diretório com uma chamada em andamento (só `.tmp.raw`) | Tratamento explícito de `.mp3` legado ou de `.tmp.raw` em andamento, com log dedicado — descartado por redundante: o `None` já existente cobre os dois cenários sem introduzir um caminho de código exclusivo | 🟢 |
| D-07 | `generate_stereo` produz `stereo.wav` (`-codec:a pcm_s16le`, `-ar 16000`, mantém `amerge=inputs=2`/`-ac 2`) | RN-08 — estéreo publicado no SMB passa a ser WAV fiel, não MP3 | Manter MP3 estéreo e só trocar os monos — descartada, contraria decisão explícita do usuário em `/reversa-clarify` (seção 9, dúvida 2) | 🟢 |
| D-08 | `build_remote_name(..., extension: str = "wav", include_collision_suffix=False)`; os dois call-sites em `_process_call_unbounded` passam `extension="wav"` explicitamente | RF-03 pede literalmente que a função "deixe de fixar `.mp3` e passe a aceitar a extensão como parâmetro" | Duplicar a função para um nome com sufixo `_wav` — descartada, quebra o precedente de uma única função de nomenclatura remota | 🟢 |
| D-09 | Novo módulo `src/workers/recording_consumers.py` com `mark_consumed(call_dir, consumer: str)` (escrita atômica de `.consumed-<consumer>`) e `is_fully_consumed(call_dir, required: Iterable[str]) -> bool` | RF-08 pede um mecanismo que consumidores futuros (`013`) registrem "sem exigir redesenho" — um marcador por consumidor, verificado contra uma lista de exigidos, atende isso sem acoplar `audio_cleanup` a `smb_sync` além do que já existe (`audio_cleanup` já importa `has_valid_lease` de `smb_sync`) | Colocar a função dentro de `smb_sync.py` (que já tem ~700 linhas e cresceria mais) ou dentro de `audio_cleanup.py` (inverteria a direção da dependência: cleanup passaria a ser importado por smb_sync) | 🟡 |
| D-10 | Lista de consumidores exigidos vem de `settings.RECORDING_REQUIRED_CONSUMERS: list[str] = ["smb"]` (pydantic-settings, mesmo padrão de `SMB_*`) | Torna a adesão da `013` como segundo consumidor uma mudança de configuração (env var), não de código — é literalmente o "sem exigir redesenho" pedido pela RF-08 | Lista hardcoded em `recording_consumers.py` — descartada, exigiria alterar código-fonte quando `013` for mergeada | 🟢 |
| D-11 | `smb_sync._process_call_unbounded` chama `mark_consumed(call_dir, "smb")` logo após `_publish_with_retry` retornar com sucesso, antes do `stereo_path.unlink()` | É o único ponto onde o worker já sabe que o SMB confirmou recebimento (o mesmo evento que grava `status: "done"` no transfer log) | Marcar consumo a partir do `transfer_log.json` (releitura do estado) — descartada, redundante e adiciona uma segunda fonte de verdade para o mesmo fato | 🟢 |
| D-12 | `audio_cleanup.cleanup_tenant_bucket` ganha um segundo caminho: para `tx.wav`/`rx.wav` especificamente, se `is_fully_consumed(call_dir, settings.RECORDING_REQUIRED_CONSUMERS)`, remove independentemente do `mtime`; senão, cai no cutoff por TTL já existente (inalterado) | RN-07/RF-05 — exclusão por confirmação é a defesa primária, TTL continua como rede de segurança, sem duplicar a varredura `os.walk` já existente | Job ARQ dedicado disparado por evento de confirmação — descartada, adiciona um gatilho novo quando o cron de 15 min já varre o mesmo diretório | 🟢 |
| D-13 | Nenhuma migração Alembic; todo o estado de confirmação de consumo vive em filesystem (`.consumed-<consumer>`), como o `transfer_log.json` e o `.smb-processing` já vivem | Menor blast radius — dado efêmero de ciclo de vida de arquivo não precisa de coluna em `Call` nem acoplamento novo `workers → database` | Coluna `smb_confirmed_at` em `Call` — descartada, exige migração para um dado que só importa enquanto o arquivo existe em disco | 🟢 |
| D-14 | O canal é gravado em `<channel>.tmp.raw` durante toda a chamada; `finalize_call_recording` (D-04) faz `os.replace(<channel>.tmp.raw, <channel>.raw)` para cada canal presente, como parte do fechamento dos handles. `ensure_mono_pair`/`smb_sync` e `audio_cleanup` não precisam de nenhum código novo para respeitar isso — ambos já operam por nome exato de arquivo (`tx.raw`/`rx.raw`/`tx.wav`/`rx.wav`), nunca por glob, então `.tmp.raw` é invisível para eles por construção | Correção do bug encontrado nesta revisão (ver resumo, `investigation.md#6`): sem isso, `smb_sync._run_cycle` (cron independente do hangup, varre o diretório a cada `SMB_SYNC_INTERVAL_MINUTES`) trataria o `.raw` de uma chamada ainda ativa como "aguardando conversão", publicaria um recorte truncado, marcaria como consumido, e o cleanup apagaria a gravação real. Validado com `/brainstorming-multiagent` (Codex, Claude Opus, DeepSeek/OpenCode) | Marcador `.call-active` por diretório (proposta inicial desta decisão) — descartada: por ser escrita única, o `mtime` do marcador fica congelado, e o próprio `audio_cleanup` (que apaga por `mtime < cutoff` qualquer nome não explicitamente protegido) o removeria no meio de uma chamada longa, reabrindo o bug sem crash algum (achado da lente de profundidade técnica). Corrigir isso exigiria um lease renovado (como `.smb-processing`/`write_lease`), mais complexo que simplesmente não expor o nome `.raw` até a chamada acabar. Checagem por `mtime` do próprio `.raw` (lente de pragmatismo) — descartada por reintroduzir o mesmo bug de outra forma: um `.raw` "quieto" por alguns segundos (pausa na fala, supressão de silêncio upstream) seria lido como "chamada terminada" | 🟢 |
| D-15 | Chunks que chegam ao `handle_forked_stream` depois que `finalize_call_recording` já rodou para aquele `call_id` (handle já fechado e renomeado) são descartados e logados uma vez por chamada — nunca tentam escrever no handle fechado nem reabrem `.tmp.raw`/`.raw` | Sem essa guarda, um chunk tardio levantaria exceção ao escrever num arquivo fechado (pior caso: reabrir e escrever depois do `os.replace` corromperia um `.raw` que `audio_uploader`/`smb_sync` já pode estar lendo). O guarda natural é a própria ausência da entrada no dict de `raw_files` após D-04 remover — mesma estrutura de dado, sem mecanismo novo | Deixar a exceção propagar e derrubar a conexão WebSocket — descartada, hoje esse cenário é inofensivo (chunk tardio só cria uma entrada nova e abandonada em `self.buffers`); a mudança para arquivo não pode piorar esse comportamento existente | 🟢 |

## 4. Premissas

Nenhuma. O requirements não tem marcador `[DÚVIDA]` em aberto (seção 10: "Nenhuma lacuna aberta
no momento"). As três dúvidas originais já foram resolvidas em `/reversa-clarify` e incorporadas
como RN-07/RN-08/RN-09.

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| Captura ESL | `_reversa_sdd/domain.md#R42`, `esl_client.py:256` | regra-alterada | Taxa pedida ao FreeSWITCH passa de `8k` para `16000` (D-01) |
| AudioIngestor | `_reversa_sdd/code-analysis.md#3-audio`, `ingestor.py` | regra-alterada | Buffer em RAM (`self.buffers`) substituído por escrita incremental em disco por canal, com nome transitório `.tmp.raw` até a finalização (D-03/D-04/D-14/D-15) |
| Audio uploader | `_reversa_sdd/code-analysis.md#10-workers--Background-Jobs`, `audio_uploader.py` | regra-alterada | `_convert_to_mp3` → `_convert_to_wav`; job ARQ deixa de transportar bytes, opera sobre `.raw` em disco (D-02/D-05) |
| SMB backup (`011`) | `_reversa_sdd/addenda/011-smb-audio-backup.md`, `smb_sync.py` | regra-alterada | `ensure_mono_pair`/`generate_stereo`/`build_remote_name` migram para WAV; ponto de confirmação de consumo adicionado (D-06/D-07/D-08/D-11) |
| Cleanup de gravações | `_reversa_sdd/code-analysis.md#10-workers--Background-Jobs`, `audio_cleanup.py` | regra-alterada | Exclusão condicionada à confirmação de consumo, TTL como rede de segurança (D-12) |
| Mecanismo de confirmação de consumo | *(componente novo, sem origem no legado)* | componente-novo | `recording_consumers.py`: marcador por consumidor + verificação contra lista exigida (D-09/D-10) |
| Configuração | `_reversa_sdd/dependencies.md#Dependências-Core`, `config.py` | contrato-novo | `RECORDING_REQUIRED_CONSUMERS: list[str] = ["smb"]` |
| Contrato de arquivo de gravação | `_reversa_sdd/domain.md#R39`, `#R41` | contrato-alterado | Extensão `.mp3` → `.wav`, taxa 8 kHz → 16 kHz mono para canal, estéreo publicado também vira WAV (RN-02/RN-08) — ver `interfaces/recording-audio-files.md` |

## 6. Delta no modelo de dados

- Nenhuma migração PostgreSQL: nenhuma tabela, coluna ou índice muda (D-13).
- Estado novo, todo em filesystem: marcador `.consumed-<consumer>` por chamada (novo) e os
  valores `tx_path`/`rx_path`/`stereo_path` já persistidos em `smb_transfer_log.json` passam a
  apontar para `.wav`.
- Detalhe completo em `_reversa_forward/014-captura-wav-16k/data-delta.md`.

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| Arquivo de canal / estéreo de gravação (consumido por `013` e pela cópia publicada no SMB) | arquivo | `_reversa_forward/014-captura-wav-16k/interfaces/recording-audio-files.md` |

O comando `uuid_audio_stream` (ESL → FreeSWITCH) muda de parâmetro (D-01), mas seu contrato de
mensagem/resposta não muda — não justifica um arquivo de interface próprio.

## 8. Plano de migração

1. A inspeção do host de produção (2026-08-12, `df -h` + `find` em `/data/recordings`) confirmou
   tmpfs vazio — não há `.mp3` em produção para migrar ou conviver com o novo formato no corte.
2. Deploy da feature reconstrói os containers `zenith-app`/`zenith-arq-uploader` normalmente; o
   tmpfs já é recriado vazio a cada recriação de container (comportamento existente, não
   introduzido por esta feature).
3. Antes do deploy, confirmar de novo que `/data/recordings` está vazio (mesma checagem da
   inspeção); se não estiver, RF-04 garante que diretórios `.mp3`-only sejam ignorados sem erro
   pelo ciclo de backup (D-06) — não é necessário script de migração de dados.
4. Nenhum rollback de dado é necessário: reverter o código volta a gravar `.mp3`/8 kHz sem deixar
   artefato `.wav` incompatível para trás, porque o tmpfs não retém nada além da janela de
   retenção corrente.
5. **Ordem de deploy do payload do job ARQ (D-05):** `upload_recording_batch` muda de assinatura
   — deixa de aceitar `recordings: list[dict]` com bytes e passa a resolver os arquivos pelo
   `call_dir`. A feature `011` já foi pega exatamente por essa classe de problema
   (`_reversa_forward/011-smb-audio-backup/roadmap.md#D-20`: função não encontrada / produtor
   antigo em memória após reiniciar só parte dos containers). Antes de subir o código novo,
   drenar (ou tolerar perder) os jobs em voo na fila `zenith:audio-upload` — um job antigo
   `{"channel":..., "data":...}` processado pelo worker novo, ou um job novo processado pelo
   worker antigo, falha silenciosamente. Reiniciar `zenith-api-1`/`zenith-api-2` (produtores) e
   `zenith-arq-uploader` (consumidor) na mesma janela de deploy.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Gatilho duplo de finalização (D-04) mal implementado deixa handle de arquivo aberto indefinidamente se nem hangup nem desconexão do WS disparam | alto (fd leak, gravação nunca finalizada, `.tmp.raw` nunca vira `.raw`) | baixa | Idempotência via remoção da entrada do dict como guarda única; cobrir com teste que simula ordem invertida dos dois gatilhos |
| **[Fechado por D-14, registrado para rastreabilidade]** `smb_sync` converteria/publicaria/marcaria como consumido o `.raw` de uma chamada ainda ativa, e o cleanup apagaria a gravação real por baixo do handle aberto — achado da revisão `/brainstorming-multiagent` desta feature | alto (perda de gravação real) | era certa sob o desenho original (D-03 antes da revisão), não uma hipótese | D-14: canal escrito em `.tmp.raw` durante a chamada, só vira `.raw` na finalização — `smb_sync`/`audio_cleanup` não veem o transitório por construção, sem mudança de código neles |
| Pico de ocupação do tmpfs numa única chamada longa, mesmo sem concorrência: durante a janela de conversão, `<channel>.raw` (~230 MB para os dois canais numa chamada de 1h) coexiste brevemente com `<channel>.wav` recém-criado antes do `.raw` ser removido; separadamente, durante a janela de publicação SMB, `tx.wav`+`rx.wav` (~230 MB) coexistem com `stereo.wav` (conteúdo de áudio equivalente, ~230 MB) até o checksum confirmar e o estéreo ser removido — cada uma dessas janelas isoladamente já soma **~460 MB contra um tmpfs de 512 MB**, para uma única chamada de 1h, sem nenhuma chamada concorrente | alto (falha de escrita = perda de áudio, tmpfs é RAM) | baixa–média para chamadas de 1h (perfil real de duração não medido); a aritmética não depende de concorrência para ficar perto do teto | Não há correção de código que elimine as duas coexistências sem redesenhar RN-08 (decisão já tomada pelo usuário) ou aumentar o tmpfs (mudança de infra fora do escopo desta feature, decisão consciente de quem aprovar). Ação obrigatória: medir o pico real de ocupação numa chamada de teste de duração representativa (onboarding, passo de checklist) antes de considerar a feature pronta; se o perfil real de chamadas do cliente incluir chamadas longas, elevar o tamanho do `zenith_recordings_tmpfs` é a alavanca, e precisa de aprovação explícita antes do deploy |
| Dois processos escrevendo o `.tmp.raw`/marcador da mesma chamada, se a invariante "só `INSTANCE_ID==1` roda `ESLClient`/`AudioIngestor`" falhar por má configuração (não há lock distribuído, é garantida só por configuração de aplicação) | alto (PCM intercalado e irrecuperável) | baixa (risco pré-existente ao ESLClient, não introduzido por esta feature — a escala de dano muda de "trabalho duplicado" para "arquivo corrompido" porque agora há um recurso de arquivo compartilhado) | Fora do escopo desta feature (lock distribuído não foi pedido); registrado aqui por ter sido levantado explicitamente na revisão técnica (`investigation.md#6`) |
| Handles de arquivo abertos simultaneamente para muitas chamadas concorrentes esbarram em limite de file descriptors do processo | baixo | baixa | Sem dado de concorrência real hoje; não é ação desta feature, só registro do limite conhecido |
| Renomear `_convert_to_mp3` quebra o import cruzado em `smb_sync.py:30` se algum call-site for esquecido | médio (falha silenciosa em runtime, não em import) | baixa | RF-06 (suíte verde) cobre `smb_sync.py` e `audio_uploader.py`; buscar todas as ocorrências do nome antigo antes de fechar a feature |
| Payload do job ARQ de upload muda de formato (D-05) sem coordenar o deploy dos produtores/consumidor | médio (jobs em voo falham silenciosamente) | baixa–média (já aconteceu na feature `011`, mesma classe de bug) | Passo 5 do plano de migração (seção 8) |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] `pytest -v tests src` verde, incluindo `test_smb_sync.py`, `test_audio_uploader.py`,
      `test_audio_cleanup.py` e `test_esl_client.py` atualizados para o novo formato
- [ ] Veredito do `advisor()` sobre os testes escritos (regra anti-viés do `AGENTS.md`) registrado
- [ ] Chamada real de ponta a ponta confirma `tx.wav`/`rx.wav` em PCM16 mono 16 kHz (`ffprobe`)
- [ ] **Taxa efetiva confirmada por vazão, não só por rótulo do header:** bytes/s medidos no
      `.tmp.raw` crescendo durante a chamada batem com 16 kHz (não apenas o `ffprobe` do `.wav`
      final, que reporta o que foi mandado converter, não o que o FreeSWITCH de fato enviou —
      ver `onboarding.md#3`)
- [ ] Ciclo de backup SMB publica `stereo.wav` com checksum conferido
- [ ] Exclusão por confirmação de consumo observada numa chamada de teste, antes do TTL expirar
- [ ] Pico real de ocupação do `zenith_recordings_tmpfs` medido numa chamada de teste de duração
      representativa (risco de capacidade, seção 9)
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-12 | Versão inicial gerada por `/reversa-plan` | reversa |
| 2026-08-13 | Revisão via `advisor()` + `/brainstorming-multiagent` (Codex, Claude Opus, DeepSeek/OpenCode): D-03/D-04 trocam `.raw` direto por `.tmp.raw`+rename (D-14) para fechar corrida real com `smb_sync`; D-15 (chunk tardio pós-finalização) adicionada; D-02 corrigida (justificativa anterior sobre `wave` estava errada); riscos de pico de tmpfs (~460 MB para uma chamada de 1h) e de ordenação de deploy do payload ARQ (D-05) adicionados com aritmética/precedente concretos | reversa |
