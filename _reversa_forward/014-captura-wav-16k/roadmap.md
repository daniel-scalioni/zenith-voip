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
Enquanto a chamada está ativa, `.raw` simplesmente não existe e o `smb_sync` continua sem
reconhecer `.tmp.raw`. A revisão de 2026-08-14 corrigiu, porém, uma premissa errada da versão
anterior: `audio_cleanup` não opera por nomes exatos; ele varre todo arquivo por `mtime` e precisa
ser alterado para nunca remover um temporário ativo. Por isso o nome transitório é combinado com
lease renovável por estágio e cleanup de órfãos em duas rodadas (D-16 a D-19). Detalhe completo
da consulta em `investigation.md#6` e `#7`.

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

O volume `zenith_recordings_tmpfs` passa de 512 MB para 2 GiB. Um guardião de capacidade no
`AudioIngestor` admite uma nova gravação apenas quando o uso atual, o crescimento restante das
gravações ativas, a reserva da nova chamada de até 5 min e o headroom de processamento ainda
deixam 20% livres. Se a projeção falhar, somente o novo stream de gravação é recusado; a chamada
SIP e gravações já admitidas continuam. A admissão retorna com 30% projetados para evitar
flapping. O gate operacional usa 30 chamadas simultâneas e bloqueia o rollout se a margem real
ficar abaixo de 20% (D-20/D-21).

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
| D-02 | Conversão `.raw → .wav` reaproveita o subprocess `ffmpeg`: a entrada PCM muda explicitamente de `-ar 8000` para `-ar 16000`; a saída usa `-c:a pcm_s16le -ar 16000 -ac 1`, escreve `<channel>.tmp.wav` e só publica `<channel>.wav` por `os.replace` após sucesso | Sem mudar a taxa de entrada, o ffmpeg interpretaria PCM 16 kHz como 8 kHz e produziria áudio em velocidade errada mesmo com header final 16 kHz. O temporário impede consumidor de ler saída parcial | Escrever direto no nome final; módulo `wave` como segundo mecanismo | 🟢 |
| D-03 | `AudioIngestor` mantém `raw_files: dict[call_id, dict[channel, BinaryIO]]`; abre `tx.tmp.raw`/`rx.tmp.raw` sob demanda no primeiro chunk daquele canal (`RECORDINGS_PATH/<tenant_id>/<call_id>/<channel>.tmp.raw`) e escreve cada chunk recebido do WebSocket imediatamente; `self.buffers` é removido | RN-09/RF-09 pedem escrita incremental sem acúmulo em RAM. O sufixo `.tmp.raw` (em vez de `.raw` direto) é o que fecha a corrida com `smb_sync` descrita no resumo — ver D-14. O `tenant_id` já está disponível em `stream_metadata` desde `register_stream_metadata` (CHANNEL_ANSWER) | Escrever direto em `<channel>.raw` desde o primeiro chunk (redação inicial desta decisão) — descartada depois da revisão multiagente por deixar `.raw` de uma chamada ativa indistinguível de um `.raw` de chamada finalizada aguardando conversão | 🟢 |
| D-04 | `finalize_call_recording(call_id)` reivindica sincronamente o estado completo da gravação com um único `pop` antes de qualquer `await`; esse estado contém handles, paths e metadados necessários. O vencedor entre `CHANNEL_HANGUP` e o `finally` do WebSocket fecha os handles, publica `.raw`, remove o lease de captura e enfileira upload; o segundo é no-op. `stream_metadata` só é removido depois da tentativa de finalização | Os transportes ESL e WebSocket não têm ordem garantida. Guardar metadados junto do estado reivindicado impede que uma desconexão anterior ao hangup deixe `.tmp.raw` órfão por perda de `tenant_id` | Confiar apenas no hangup; remover metadata antes de finalizar; inserir `await` entre consultar e reivindicar o estado | 🟢 |
| D-05 | `enqueue_recording_upload(tenant_id, call_id)` deixa de transportar bytes e usa `_job_id` determinístico por tenant/chamada; `upload_recording_batch` lista os `.raw` estáveis e converte um canal por vez sob `.conversion-processing`. Job duplicado ou payload antigo vira no-op seguro quando o estado esperado não existe | Fecha o segundo acúmulo em memória e impede dois retries de escreverem simultaneamente no mesmo `<channel>.tmp.wav` | Manter bytes no Redis; confiar apenas na ausência casual de retries; temporário único por job, que quebraria o contrato de nomes | 🟢 |
| D-06 | `ensure_mono_pair` procura `tx.wav`/`rx.wav` em vez de `tx.mp3`/`rx.mp3`; se nenhum dos dois existir (nem `.raw` pendente), retorna `None` como hoje — sem nenhum tratamento especial para `.tmp.raw`, que a função nunca chega a enxergar pelo nome | Mesmo comportamento de "pendente, sem exceção" que já existe para pares incompletos cobre RF-04 sem código novo: um diretório só com `.mp3` legado (sem `.raw`/`.wav`) simplesmente nunca completa o par e o ciclo de backup o ignora, como já faz hoje para qualquer par incompleto — e agora, pelo mesmo motivo, também ignora sem erro um diretório com uma chamada em andamento (só `.tmp.raw`) | Tratamento explícito de `.mp3` legado ou de `.tmp.raw` em andamento, com log dedicado — descartado por redundante: o `None` já existente cobre os dois cenários sem introduzir um caminho de código exclusivo | 🟢 |
| D-07 | `generate_stereo` escreve `stereo.tmp.wav` (`-codec:a pcm_s16le`, `-ar 16000`, `amerge=inputs=2`, `-ac 2`) e publica `stereo.wav` por `os.replace` | RN-08 e RN-10: estéreo publicado no SMB passa a WAV fiel e nunca fica visível parcialmente | Manter MP3 estéreo; escrever diretamente em `stereo.wav` | 🟢 |
| D-08 | `build_remote_name(..., extension: str = "wav", include_collision_suffix=False)`; os dois call-sites em `_process_call_unbounded` passam `extension="wav"` explicitamente | RF-03 pede literalmente que a função "deixe de fixar `.mp3` e passe a aceitar a extensão como parâmetro" | Duplicar a função para um nome com sufixo `_wav` — descartada, quebra o precedente de uma única função de nomenclatura remota | 🟢 |
| D-09 | Novo módulo `src/workers/recording_consumers.py` com `mark_consumed(call_dir, consumer: str)` (escrita atômica de `.consumed-<consumer>`) e `is_fully_consumed(call_dir, required: Iterable[str]) -> bool` | RF-08 pede um mecanismo que consumidores futuros (`013`) registrem "sem exigir redesenho" — um marcador por consumidor, verificado contra uma lista de exigidos, atende isso sem acoplar `audio_cleanup` a `smb_sync` além do que já existe (`audio_cleanup` já importa `has_valid_lease` de `smb_sync`) | Colocar a função dentro de `smb_sync.py` (que já tem ~700 linhas e cresceria mais) ou dentro de `audio_cleanup.py` (inverteria a direção da dependência: cleanup passaria a ser importado por smb_sync) | 🟡 |
| D-10 | Lista de consumidores exigidos vem de `settings.RECORDING_REQUIRED_CONSUMERS: list[str] = ["smb"]` (pydantic-settings, mesmo padrão de `SMB_*`) | Torna a adesão da `013` como segundo consumidor uma mudança de configuração (env var), não de código — é literalmente o "sem exigir redesenho" pedido pela RF-08 | Lista hardcoded em `recording_consumers.py` — descartada, exigiria alterar código-fonte quando `013` for mergeada | 🟢 |
| D-11 | `smb_sync._process_call_unbounded` chama `mark_consumed(call_dir, "smb")` logo após `_publish_with_retry` retornar com sucesso, antes do `stereo_path.unlink()` | É o único ponto onde o worker já sabe que o SMB confirmou recebimento (o mesmo evento que grava `status: "done"` no transfer log) | Marcar consumo a partir do `transfer_log.json` (releitura do estado) — descartada, redundante e adiciona uma segunda fonte de verdade para o mesmo fato | 🟢 |
| D-12 | `audio_cleanup.cleanup_tenant_bucket` ganha um segundo caminho: para `tx.wav`/`rx.wav` especificamente, se `is_fully_consumed(call_dir, settings.RECORDING_REQUIRED_CONSUMERS)`, remove independentemente do `mtime`; senão, cai no cutoff por TTL já existente (inalterado) | RN-07/RF-05 — exclusão por confirmação é a defesa primária, TTL continua como rede de segurança, sem duplicar a varredura `os.walk` já existente | Job ARQ dedicado disparado por evento de confirmação — descartada, adiciona um gatilho novo quando o cron de 15 min já varre o mesmo diretório | 🟢 |
| D-13 | Nenhuma migração Alembic; todo o estado de confirmação de consumo vive em filesystem (`.consumed-<consumer>`), como o `transfer_log.json` e o `.smb-processing` já vivem | Menor blast radius — dado efêmero de ciclo de vida de arquivo não precisa de coluna em `Call` nem acoplamento novo `workers → database` | Coluna `smb_confirmed_at` em `Call` — descartada, exige migração para um dado que só importa enquanto o arquivo existe em disco | 🟢 |
| D-14 | O canal é gravado em `<channel>.tmp.raw` durante toda a chamada e só vira `<channel>.raw` por `os.replace` após fechar o handle. `ensure_mono_pair` continua a ignorar o transitório por nome; `audio_cleanup`, ao contrário da redação anterior, precisa mudar porque hoje varre todo arquivo por `mtime` | O nome fecha a corrida de consumo prematuro pelo SMB; lease + cleanup em duas rodadas fecham a corrida de exclusão do transitório ativo | `.raw` direto; `.call-active` de escrita única; heurística de silêncio/mtime | 🟢 |
| D-15 | Chunks que chegam ao `handle_forked_stream` depois que `finalize_call_recording` já rodou para aquele `call_id` (handle já fechado e renomeado) são descartados e logados uma vez por chamada — nunca tentam escrever no handle fechado nem reabrem `.tmp.raw`/`.raw` | Sem essa guarda, um chunk tardio levantaria exceção ao escrever num arquivo fechado (pior caso: reabrir e escrever depois do `os.replace` corromperia um `.raw` que `audio_uploader`/`smb_sync` já pode estar lendo). O guarda natural é a própria ausência da entrada no dict de `raw_files` após D-04 remover — mesma estrutura de dado, sem mecanismo novo | Deixar a exceção propagar e derrubar a conexão WebSocket — descartada, hoje esse cenário é inofensivo (chunk tardio só cria uma entrada nova e abandonada em `self.buffers`); a mudança para arquivo não pode piorar esse comportamento existente | 🟢 |
| D-16 | Novo módulo neutro `src/audio/recording_lifecycle.py` centraliza escrita/leitura/renovação/remoção de leases `.*-processing`, com allowlist de nomes, JSON versionado, owner UUID, `expires_at` UTC e escrita atômica. Capture renova `.capture-processing`; uploader usa `.conversion-processing`; SMB mantém `.smb-processing` pela mesma API | Evita nomes e validação duplicados entre `audio` e `workers`; um arquivo corrompido/expirado nunca protege diretório indefinidamente | Funções hardcoded dentro de `smb_sync`; aceitar qualquer arquivo que termine em `-processing` sem validar | 🟢 |
| D-17 | Lease de captura é criado antes do primeiro `.tmp.raw`, renovado por heartbeat de 30 s com validade de 120 s e removido somente após finalizar/publicar ou abandonar a captura. Falha de criação/renovação impede continuidade segura da gravação, fecha apenas o stream de áudio e registra alerta; a chamada SIP não é interrompida | `mtime` do áudio não é heartbeat e chamadas podem ficar silenciosas. Validade 4× heartbeat tolera jitter sem depender do cron de 15 min | `.call-active` de escrita única; registry apenas em memória; PID via `/proc` entre containers | 🟢 |
| D-18 | `audio_cleanup` classifica apenas temporários locais reconhecidos (`tx.tmp.raw`, `rx.tmp.raw`, `tx.tmp.wav`, `rx.tmp.wav`, `stereo.tmp.wav`). Sem lease válido, a primeira rodada grava/atualiza `.cleanup-candidates.json` com `first_seen` e fingerprint (`inode`, `size`, `mtime_ns`); a segunda, após ao menos 15 min, revalida lease e fingerprint antes de excluir. Mudança ou lease reaparecido cancela a candidatura | Implementa RN-12 sem usar mtime como prova de atividade; fingerprint serve somente como identidade entre rodadas | Excluir por idade numa passada; excluir todo `*.tmp*`; recuperar/promover parcial | 🟢 |
| D-19 | O sweep genérico nunca remove `.*-processing`, `.consumed-*`, `.cleanup-candidates.json` nem temporários de áudio. WAVs finais plenamente consumidos podem ser removidos no primeiro ciclo; finais não consumidos usam TTL. `final.wav.tmp` remoto é varrido pelo próprio SMB em duas observações do transfer log, nunca pelo cleanup local | Separa estado de controle, temporário local e remoto; consumo confirmado já encerrou o contrato do final | Aplicar duas rodadas também aos finais consumidos; varrer SMB pelo worker local | 🟢 |
| D-20 | Novo `RecordingCapacityGuard` em `src/audio/capacity.py`: antes de aceitar a primeira gravação de uma chamada, calcula `used + crescimento_restante_ativas + reserva_nova(19_200_000 B) + headroom_processamento`; admite somente se o projetado ocupar no máximo 80% de 2 GiB. Em modo degradado, só reabre admissão quando a projeção cai a 70% | Uma leitura instantânea de espaço livre não reserva o crescimento já admitido. Histerese 80/70 evita flapping | Checar somente `df` atual; apagar candidato na primeira rodada; derrubar chamada SIP | 🟢 |
| D-21 | `docker-compose.app.yml` configura `zenith_recordings_tmpfs` com 2 GiB. O gate usa 30 chamadas simultâneas de até 5 min; 512 MB deixa de ser alternativa ou decisão futura | Decisão humana 1A; baseline de captura é ~576 MB decimal antes dos transitórios | 4/6 GiB preventivos; manter 512 MB e decidir após teste | 🟢 |
| D-22 | Telemetria adiciona gauges/counters para ocupação, bytes reservados, modo degradado, gravações recusadas, temporários candidatos/excluídos e falhas de lease. Alertas são emitidos uma vez por transição, não por chunk | RF-12 exige operação observável sem `print()` | Log por chunk; métrica apenas no cleanup de 15 min | 🟢 |
| D-23 | Cron cleanup recebe `unique=True` e `job_id` próprio; exclusões capturam `FileNotFoundError` por arquivo. Uploader/SMB preservam single-writer com job id/lease e resultados idempotentes | Evita que corrida entre réplicas aborte a rodada ou corrompa temporário determinístico | Lock apenas em memória como garantia distribuída | 🟢 |
| D-24 | Rollout drena `zenith:audio-upload`, sobe API/uploader/SMB/cleanup coordenadamente, altera somente recursos `zenith-*`, valida rollback e executa chamada real/SMB/cleanup/capacidade antes do sync e da retomada da 013 | D-05 muda contrato da fila; RN-14 exige prova operacional completa | Restart parcial; retomar 013 após apenas testes locais | 🟢 |

## 4. Premissas

Nenhuma. O requirements não tem marcador `[DÚVIDA]` em aberto (seção 10: "Nenhuma lacuna aberta
no momento"). As três dúvidas originais já foram resolvidas em `/reversa-clarify` e incorporadas
como RN-07/RN-08/RN-09.

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| Captura ESL | `_reversa_sdd/domain.md#R42`, `esl_client.py:256` | regra-alterada | Taxa pedida ao FreeSWITCH passa de `8k` para `16000` (D-01) |
| AudioIngestor | `_reversa_sdd/code-analysis.md#3-audio`, `ingestor.py` | regra-alterada | Buffer em RAM substituído por escrita incremental, finalização idempotente, lease de captura e admissão por capacidade (D-03/D-04/D-14/D-15/D-17/D-20) |
| Ciclo de vida da gravação | *(componente novo)* | componente-novo | `recording_lifecycle.py` centraliza leases nomeados e validação compartilhada entre captura e workers (D-16) |
| Guardião de capacidade | *(componente novo)* | componente-novo | `capacity.py` reserva crescimento máximo, mantém histerese 80/70 e recusa somente novas gravações (D-20/D-22) |
| Audio uploader | `_reversa_sdd/code-analysis.md#10-workers--Background-Jobs`, `audio_uploader.py` | regra-alterada | `_convert_to_wav`, payload por path, job idempotente e lease de conversão (D-02/D-05/D-16) |
| SMB backup (`011`) | `_reversa_sdd/addenda/011-smb-audio-backup.md`, `smb_sync.py` | regra-alterada | WAV mono/estéreo, confirmação de consumo, lease compartilhado e coleta de temporário remoto órfão (D-06/D-07/D-08/D-11/D-19) |
| Cleanup de gravações | `_reversa_sdd/code-analysis.md#10-workers--Background-Jobs`, `audio_cleanup.py` | regra-alterada | Finais consumidos/TTL separados de temporários órfãos em duas rodadas; controles protegidos e cron idempotente (D-12/D-18/D-19/D-23) |
| Mecanismo de confirmação de consumo | *(componente novo, sem origem no legado)* | componente-novo | `recording_consumers.py`: marcador por consumidor + verificação contra lista exigida (D-09/D-10) |
| Configuração/infra | `_reversa_sdd/dependencies.md#Dependências-Core`, `config.py`, `docker-compose.app.yml` | contrato-alterado | Consumidores exigidos, limites de lease/capacidade e tmpfs de 2 GiB (D-10/D-17/D-20/D-21) |
| Contrato de arquivo de gravação | `_reversa_sdd/domain.md#R39`, `#R41` | contrato-alterado | Extensão `.mp3` → `.wav`, taxa 8 kHz → 16 kHz mono para canal, estéreo publicado também vira WAV (RN-02/RN-08) — ver `interfaces/recording-audio-files.md` |

## 6. Delta no modelo de dados

- Nenhuma migração PostgreSQL: nenhuma tabela, coluna ou índice muda (D-13).
- Estado novo, todo em filesystem: marcadores `.consumed-<consumer>`, leases nomeados e
  `.cleanup-candidates.json` por chamada; os
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

1. Antes da mudança remota, passar suíte, cobertura, Alembic e revisão independente; gerar plano
   de rollback com as revisões/imagens `zenith-*` atuais.
2. Confirmar que `/data/recordings` está vazio ou drenado e que `zenith:audio-upload` não contém
   jobs antigos. Não apagar gravação ou fila sem inspeção explícita.
3. Alterar `zenith_recordings_tmpfs` para 2 GiB e atualizar coordenadamente somente
   `zenith-api-1`, `zenith-api-2`, `zenith-arq-uploader`, `zenith-arq-smb-sync` e
   `zenith-arq-cleanup`; nenhum container de outro prefixo é tocado.
4. Se `/data/recordings` não estiver vazio,
   inspeção); se não estiver, RF-04 garante que diretórios `.mp3`-only sejam ignorados sem erro
   pelo ciclo de backup (D-06) — não é necessário script de migração de dados.
5. **Ordem de deploy do payload do job ARQ (D-05):** `upload_recording_batch` muda de assinatura
   — deixa de aceitar `recordings: list[dict]` com bytes e passa a resolver os arquivos pelo
   `call_dir`. A feature `011` já foi pega exatamente por essa classe de problema
   (`_reversa_forward/011-smb-audio-backup/roadmap.md#D-20`: função não encontrada / produtor
   antigo em memória após reiniciar só parte dos containers). Antes de subir o código novo,
   drenar (ou tolerar perder) os jobs em voo na fila `zenith:audio-upload` — um job antigo
   `{"channel":..., "data":...}` processado pelo worker novo, ou um job novo processado pelo
   worker antigo, falha silenciosamente. Reiniciar `zenith-api-1`/`zenith-api-2` (produtores) e
   `zenith-arq-uploader` (consumidor) na mesma janela de deploy.
6. Executar chamada real, medir 32.000 bytes/s por canal, validar WAV mono/estéreo, checksum SMB,
   consumo, cleanup em duas rodadas, modo degradado e margem de 20%.
7. Se qualquer gate operacional falhar, reverter em conjunto os serviços `zenith-*` afetados e o
   tamanho/configuração do volume; não retomar a 013.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Gatilho duplo de finalização (D-04) mal implementado deixa handle de arquivo aberto indefinidamente se nem hangup nem desconexão do WS disparam | alto (fd leak, gravação nunca finalizada, `.tmp.raw` nunca vira `.raw`) | baixa | Idempotência via remoção da entrada do dict como guarda única; cobrir com teste que simula ordem invertida dos dois gatilhos |
| **[Fechado por D-14/D-17/D-18]** SMB ou cleanup agem sobre captura ativa | alto | certa no desenho original | `.tmp.raw` invisível ao SMB, lease de captura e duas rodadas para o cleanup |
| Pico com 30 chamadas de 5 min, conversões e backlog reduz a margem de 2 GiB | alto | média | Reserva de crescimento + headroom, histerese 80/70, teste real bloqueante e métricas (D-20/D-22) |
| Temporário órfão acumula por até duas rodadas | médio | baixa–média | Admissão considera uso real/backlog; cleanup registra candidatos; alerta crítico impede saturação silenciosa |
| Dois jobs uploader ou dois ciclos de cleanup concorrem | alto | baixa | `_job_id`, lease por estágio, cron unique, operações idempotentes e testes de race (D-05/D-23) |
| Renovação de lease falha por ENOSPC e o produtor continua sem proteção | alto | baixa | Falha de lease aborta somente o estágio de gravação/processamento, preserva SIP e ativa modo degradado |
| `final.wav.tmp` permanece no SMB após crash | médio | baixa | Worker SMB registra duas observações e remove órfão remoto sem upload ativo (D-19) |
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
- [ ] Cleanup em duas rodadas descarta temporário órfão e preserva temporário com lease renovado
- [ ] Modo degradado recusa nova gravação sem derrubar SIP e sai com 30% projetados
- [ ] Teste de 30 chamadas simultâneas de até 5 min mantém ao menos 20% livre em 2 GiB
- [ ] Rollout e rollback limitados a recursos `zenith-*`, chamada real aprovada
- [ ] Adendo `/reversa-sync` da 014 criado antes de retomar a 013
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-12 | Versão inicial gerada por `/reversa-plan` | reversa |
| 2026-08-13 | Revisão via `advisor()` + `/brainstorming-multiagent` (Codex, Claude Opus, DeepSeek/OpenCode): D-03/D-04 trocam `.raw` direto por `.tmp.raw`+rename (D-14) para fechar corrida real com `smb_sync`; D-15 (chunk tardio pós-finalização) adicionada; D-02 corrigida (justificativa anterior sobre `wave` estava errada); riscos de pico de tmpfs (~460 MB para uma chamada de 1h) e de ordenação de deploy do payload ARQ (D-05) adicionados com aritmética/precedente concretos | reversa |
| 2026-08-14 | Plano revisado após consultas Claude/Gemini/DeepSeek: D-02/D-04/D-05/D-07/D-14 corrigidas; D-16 a D-24 adicionam leases, cleanup em duas rodadas, coleta remota, capacidade 2 GiB com reserva/histerese, telemetria, idempotência e rollout completo antes da 013 | reversa |
