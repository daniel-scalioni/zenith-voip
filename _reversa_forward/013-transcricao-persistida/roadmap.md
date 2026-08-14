# Roadmap: Transcrição persistida (F1 — Épico 2: Qualidade do Atendimento)

> Identificador: `013-transcricao-persistida`
> Data: `2026-08-12`
> Requirements: `_reversa_forward/013-transcricao-persistida/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Um novo worker ARQ (`arq-transcript`, fila exclusiva `zenith:transcript`) roda em cron polling
sobre `RECORDINGS_PATH/*/*` — mesmo padrão já usado por `run_smb_sync` (feature `011`) — buscando
pares `tx.mp3`/`rx.mp3` ainda não transcritos (idempotência checada por existência de linhas
`Transcript` para o `call_id`, não por um transfer-log JSON separado). Para cada par encontrado,
divide os arquivos em janelas via `ffmpeg` (já presente na imagem), alimenta cada janela ao
`WhisperCppSTT` (corrigindo o bug de detecção do binário encontrado nesta etapa), grava os
segmentos diretamente em `Transcript` (Postgres, transação única, substituição idempotente por
`call_id`, sem a indireção via Redis List de `TranscriptPersister`), e gera um `.md` consolidado
publicado no SMB com o mesmo nome-base e diretório do `stereo.mp3` correspondente, reaproveitando
as funções de nomeação/conexão já existentes em `src/workers/smb_sync.py`. Nenhuma análise de
qualidade (sentimento, auditoria, anomalia) faz parte desta feature.

## 2. Princípios aplicados

`.reversa/principles.md` não existe neste projeto — nenhum princípio formal registrado ainda.
N/a.

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|----------------------------|-------------|
| D-01 | Descoberta por cron polling sobre `RECORDINGS_PATH/*/*` verificando `tx.mp3`+`rx.mp3` prontos, em vez de hook síncrono disparado no `CHANNEL_HANGUP`. | Mesmo padrão já usado e validado por `run_smb_sync`/`_run_cycle` (`src/workers/smb_sync.py:663-708`, feature `011-smb-audio-backup`) — reaproveitar em vez de inventar um segundo mecanismo de trigger. | Hook direto no `esl_client.py::_handle_channel_hangup` (rejeitada: acopla o worker de qualidade ao caminho crítico de telefonia, contra RN-04) | 🟢 |
| D-02 | Fila e worker exclusivos: `arq-transcript` / `zenith:transcript`, mesmo princípio de isolamento já aplicado a `arq-uploader`/`arq-cleanup`/`arq-smb-sync`. | `_reversa_forward/011-smb-audio-backup/requirements.md#RF-13` ("Isolar os workers ARQ operacionais em filas exclusivas") | Reaproveitar `zenith:smb-sync` ou `zenith:audio-upload` (rejeitada: mistura responsabilidades, um job lento de STT atrasaria upload/backup) | 🟢 |
| D-03 | Descoberta (o polling deve pular esta chamada?) usa **dois** sinais, não um: `Transcript` já existe para o `call_id` **E** o `.md` já foi confirmado publicado no SMB (checagem direta do arquivo remoto, mesmo padrão de checksum que `011` já usa antes de re-subir o `.mp3`). Sem transfer-log JSON paralelo — Postgres + SMB (verificado diretamente) são as duas fontes de verdade, não uma terceira. | Corrige contradição encontrada na revisão crítica (`/brainstorming-multiagent`, Codex CLI, 2026-08-12): um único `EXISTS` confundia "não reprocessar na descoberta" com "escrita idempotente no banco" (D-07) — são dois momentos diferentes do pipeline, cada um com sua própria verificação | Um único log JSON paralelo tipo `011` (rejeitada: estado triplicado — banco + SMB + log — mesma classe de risco de divergência do GAP-25/GAP-RE-07) | 🟢 |
| D-04 | Dividir `tx.mp3`/`rx.mp3` em janelas de duração fixa via `ffmpeg` (já instalado na imagem, `Dockerfile:5-8`) antes de alimentar o `WhisperCppSTT`; duração exata da janela fica para o `/reversa-to-do`. | Mesmo mecanismo de chunking (`ffmpeg`, corte preciso) já usado pela skill do projeto `.agents/skills/audio-transcript-long/scripts/transcribe.py`, evita estourar memória em chamadas mais longas | Transcrever o arquivo inteiro de uma vez (rejeitada: sem necessidade para chamadas curtas, mas arriscado para outliers; sem chunking não há paralelismo nem escrita incremental) | 🟡 |
| D-05 | Corrigir `WhisperCppSTT.__init__`/`transcribe()` (`src/services/stt_whisper.py:8-16`): `os.path.exists(self.whisper_binary)` testa o nome relativo `"whisper-cpp"` contra o diretório de trabalho, não contra `$PATH` — nunca encontra o binário mesmo instalado corretamente. Trocar para `shutil.which(self.whisper_binary)`. | Bug encontrado por leitura direta do código nesta etapa de planejamento; sem o fix, RF-01 não roda em nenhum ambiente, mesmo com o binário instalado | n/a — é um bug, não uma escolha de design | 🟢 |
| D-06 | **Imagem/container dedicados** para o worker de transcrição (`zenith-transcript`, `Dockerfile` próprio com build/instalação do `whisper-cpp` + modelo), **não** a mesma imagem de `fastapi-1`/`fastapi-2`, com `deploy.resources.limits` (CPU e memória) explícitos e `max_jobs`/concorrência 1 (processamento sequencial) no `WorkerSettings`. | Revisado na revisão crítica (`/brainstorming-multiagent`, Nemotron/OpenCode, 2026-08-12): o host de produção (10.10.10.11) roda FreeSWITCH (RTP em tempo real, sensível a jitter) e Ollama (Mistral 7B, CPU) **sem nenhum `deploy.resources.limits` configurado em lugar nenhum do `docker-compose.app.yml`** — misturar um worker de STT (CPU-bound) na mesma imagem/host do FastAPI sem cap explícito arrisca contenção de CPU que degrada chamadas em andamento. Container e limites próprios isolam a falha e tornam o custo de CPU explícito e controlável | Mesma imagem do FastAPI sem limites (decisão original desta feature, revertida nesta revisão — ver seção 9, risco de contenção de CPU) | 🟢 |
| D-07 | Persistência **do banco** idempotente via `pg_advisory_xact_lock(hashtext(call_id))` + delete+insert numa única transação por chamada — protege contra duas execuções concorrentes do mesmo `call_id` (ex.: dois disparos de polling sobrepostos). **Sem** reutilizar `TranscriptPersister.buffer_transcript`/`flush_batch` (`src/workers/transcript_persist.py`). Distinto da checagem de descoberta (D-03): esta é sobre concorrência de escrita, não sobre "já processei essa chamada?". | Decisão tomada em `/reversa-clarify` após consulta `/brainstorming-multiagent` (Codex CLI + DeepSeek/OpenCode, convergentes): o fluxo `LRANGE → commit → DEL` do `TranscriptPersister` não protege nada num processamento em lote sobre arquivo já em disco e tem janela real de duplicação em retry. O advisory lock foi acrescentado na revisão crítica seguinte (Codex CLI) para cobrir concorrência entre execuções, que o `delete+insert` sozinho não cobre | Corrigir só o bug `metadata`→`extra_metadata` e manter a indireção via Redis List (rejeitada pelas duas lentes consultadas — ver `requirements.md#9`); `delete+insert` sem lock (rejeitada na revisão crítica: duas execuções concorrentes do mesmo `call_id` podem intercalar delete/insert e produzir estado inconsistente) | 🟢 |
| D-08 | Reaproveitar `build_remote_directory`/`build_remote_name`/conexão `SMBConnection` de `src/workers/smb_sync.py` para nomear e publicar o `.md`, em vez de um client SMB novo. | RN-03 exige mesmo nome-base/diretório do `stereo.mp3`; a lógica de nomeação e conexão já existe, testada, na feature `011` | Implementar client SMB próprio (rejeitada: duplicação direta do que já existe e já foi validado em produção) | 🟢 |
| D-09 | **Prontidão do áudio de origem**: reaproveitar a MESMA garantia já usada pela feature `011` (`RF-09`: `tx.mp3`/`rx.mp3` só existem como arquivo final após rename atômico do produtor; enquanto convertendo, existe `.raw` ou `.tmp.mp3`) — o worker de transcrição só processa um par cujos dois arquivos finais (`.mp3`, sem `.tmp`) já existem. Não inventa um segundo mecanismo de "arquivo pronto". | Revisão crítica (Codex CLI) apontou risco real de o polling encontrar um par ainda sendo escrito. A feature `011` já resolve exatamente esse problema para os mesmos arquivos — reaproveitar em vez de reinventar | Mecanismo de prontidão próprio (rejeitada: duplicaria uma garantia que já existe e já foi validada em produção) | 🟢 |
| D-10 | **Proteção contra o `audio_cleanup`**: o worker de transcrição adquire/renova o mesmo tipo de lease que `011` já usa (`RF-11`: lease UTC de 120s renovado a cada 30s) para proteger o diretório da chamada contra o cleanup enquanto processa, cobrindo o risco de RN-05 (transcrever antes da limpeza remover os arquivos) de forma ativa, não só por cadência de disparo. | Revisão crítica (Codex CLI): "monitorar a fila" (mitigação original, seção 9) detecta o problema mas não o previne; a `011` já tem lease para exatamente esse cenário (proteger uma chamada em processamento contra o cleanup) | Confiar só na cadência do polling coincidir com o ciclo de cleanup (rejeitada: falha sob fila cheia ou pico de chamadas, sem proteção ativa) | 🟢 |
| D-11 | **Isolamento por tenant já é estrutural, não precisa de coluna nova**: `Transcript` é `TenantBase` (`src/database/models.py:13,161`) — vive fisicamente no schema `tenant_<id>`, schema-per-tenant. Colisão de `call_id` entre tenants é impossível por construção (schemas distintos = tabelas distintas). O advisory lock (D-07) é escopado à sessão/schema do tenant conectado. | Revisão crítica (Codex CLI) levantou risco de `call_id` não ser tenant-aware; confirmado por leitura direta do código que a arquitetura de multitenancy já garante isso — registrado aqui como esclarecimento, não como decisão nova | n/a — não é uma escolha, é confirmação de garantia já existente | 🟢 |

## 4. Premissas

Nenhuma — `requirements.md` não tem marcador `[DÚVIDA]` pendente (todos resolvidos em
`/reversa-clarify`, ver `requirements.md#9`).

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-------------------|--------|
| Worker de transcrição em lote (novo) | `_reversa_sdd/code-analysis.md#10-workers` | componente-novo | Novo módulo `src/workers/transcript_batch.py`: cron polling, chunking, chama `WhisperCppSTT`, persiste `Transcript`, gera/publica `.md` |
| `WhisperCppSTT` (`src/services/stt_whisper.py`) | `_reversa_sdd/code-analysis.md#8-services` | contrato-alterado | Corrige detecção do binário (D-05); primeira vez que é chamado de verdade em produção |
| `TranscriptPersister` (`src/workers/transcript_persist.py`) | `_reversa_sdd/code-analysis.md#10-workers` | componente-extinto (do caminho de execução) | Deixa de ser chamado por esta feature (D-07); arquivo permanece em disco, decisão de removê-lo ou não fica para o `/reversa-to-do` |
| Imagem Docker da aplicação (`Dockerfile`) | `_reversa_sdd/infra/deployment/design.md` | regra-alterada | Adiciona build/instalação de `whisper-cpp` + modelo (D-06) |
| `docker-compose.app.yml` | `_reversa_sdd/infra/deployment/design.md` | contrato-novo | Novo serviço `arq-transcript` (mesmo padrão de `arq-uploader`/`arq-cleanup`/`arq-smb-sync`) |
| `smb_sync.py` (`build_remote_directory`/`build_remote_name`) | `_reversa_sdd/code-analysis.md#10-workers` | regra-alterada (reaproveitado) | Reaproveitado para nomear/enviar o `.md` (D-08), sem duplicar lógica de client SMB |

## 6. Delta no modelo de dados

- Nenhum campo novo em `Transcript` — todas as colunas necessárias (`call_id`, `channel`,
  `speaker`, `text`, `confidence`, `start_time`, `end_time`, `is_final`, `extra_metadata`) já
  existem no schema. A mudança é comportamental: linhas passam a ser escritas de verdade pela
  primeira vez.
- Detalhe completo em: `_reversa_forward/013-transcricao-persistida/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|----------------------|
| Arquivo `.md` de transcrição no SMB | arquivo | `_reversa_forward/013-transcricao-persistida/interfaces/transcript-md.md` |

## 8. Plano de migração

0. **Bloqueante, antes de qualquer código**: coletar specs reais do host de produção
   (`nproc`, `free -h`, `docker info` em `10.10.10.11`) e um benchmark baseline de
   `whisper-cpp` (tempo/janela, CPU%, RAM peak) nesse mesmo host. Sem isso, qualquer limite de
   `deploy.resources.limits`/concorrência definido em D-06 é chute — achado da revisão crítica
   (Nemotron/OpenCode, seção 9).
1. Corrigir a detecção do binário em `WhisperCppSTT` (D-05).
2. Criar `Dockerfile`/imagem dedicados do worker de transcrição + `whisper-cpp` + modelo, com
   `deploy.resources.limits` definidos a partir do passo 0 (D-06).
3. Implementar o chunking dos arquivos locais via `ffmpeg` (D-04).
4. Implementar o worker `transcript_batch.py`: descoberta por polling respeitando a garantia de
   prontidão de `011` (D-01, D-09), verificação de descoberta em duas fontes (D-03), lease
   compartilhado com o cleanup (D-10).
5. Implementar a persistência em `Transcript` com advisory lock + delete/insert transacional
   (D-07), sem depender de `TranscriptPersister`.
6. Implementar a geração do `.md` consolidado e o upload SMB reaproveitando `smb_sync.py` (D-08).
7. Registrar o novo serviço `arq-transcript` (imagem própria, D-06) e fila `zenith:transcript` no
   `docker-compose.app.yml` (D-02), com `max_jobs`/concorrência 1.
8. Testes unitários (mocks em `WhisperCppSTT`, SMB, sessão Postgres) + validação com uma chamada
   real em produção, mesmo critério de aceite já usado nas features anteriores do projeto —
   incluindo observar CPU/jitter do FreeSWITCH durante o processamento (passo 0).

## 9. Riscos e mitigações

> Seção revisada em 2026-08-12 via `/brainstorming-multiagent` (Codex CLI + Nemotron/OpenCode),
> a pedido do usuário, checando especificamente preocupações de infraestrutura para uso de LLM
> local. Veredito de ambas as lentes: **o plano original não estava pronto para `/reversa-to-do`
> sem os ajustes abaixo** (já incorporados em D-06, D-09, D-10, D-11 e no passo 0 do plano de
> migração).

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|-----------------|--------------|
| **Contenção de CPU no host de produção**: FreeSWITCH (RTP em tempo real) + Ollama (Mistral 7B, CPU) + `whisper-cpp` (CPU) competem no mesmo host **sem nenhum `deploy.resources.limits` configurado em lugar nenhum do projeto** — risco de jitter/degradação de chamadas em andamento durante o processamento de transcrição. | alto | médio-alto (não medido) | Container/imagem dedicados com limites de CPU/memória explícitos (D-06) + `max_jobs=1` (processamento sequencial, sem paralelismo de janelas) + benchmark do host antes de implementar (plano de migração, passo 0). Relacionado a `GAP-PERF-01`, já registrado como lacuna aberta do Épico 1 — esta feature não deve piorar esse quadro sem medição |
| Build do binário `whisper-cpp` + modelo aumenta o tempo/tamanho da imagem Docker — mitigado por imagem separada (D-06), mas o binário ainda precisa ser buildado/baixado. | médio | médio | Cache de camada Docker na imagem dedicada `zenith-transcript` |
| Chamada excepcionalmente longa estoura memória mesmo com chunking. | alto | baixo | Fallback recursivo de corte pela metade, mesmo padrão já usado pela skill `audio-transcript-long`; `deploy.resources.limits` de memória (D-06) garante falha contida (OOM do container) em vez de derrubar o host |
| Job de transcrição não termina antes do `audio_cleanup` (a cada 15 min) remover `tx.mp3`/`rx.mp3` (RN-05), causando perda silenciosa. | alto | médio | Lease ativo compartilhado com o cleanup (D-10), não só cadência de disparo — achado da revisão crítica (Codex CLI): "monitorar a fila" detecta mas não previne |
| Descoberta processa um par `tx.mp3`/`rx.mp3` ainda sendo escrito (race com o produtor). | alto | baixo | Reaproveita a garantia de prontidão por rename atômico já validada em `011`/RF-09 (D-09) |
| Duas execuções concorrentes do mesmo `call_id` corrompem a escrita no banco. | médio | baixo | `pg_advisory_xact_lock` + delete/insert transacional (D-07) |
| Dados sensíveis (CPF, RG) presentes no `.md` e no banco sem controle de acesso adicional específico para transcrição. | alto | baixo | Mesma política de acesso já aplicada ao `stereo.mp3` no SMB (conta técnica única) — nenhuma mudança de superfície de exposição, mas atenção registrada explicitamente aqui |

## 10. Pontos ainda abertos para o `/reversa-to-do` (não bloqueiam o plano, mas precisam de decisão antes da task correspondente)

- Duração e sobreposição exata das janelas de chunking (D-04) — depende do benchmark do passo 0.
- Timeout e política de retry por job do `arq-transcript`.
- Comportamento quando um dos dois canais (`tx` ou `rx`) está ausente ou vazio (silêncio total).
- Alinhamento de timestamp entre os segmentos de `tx` e `rx` ao intercalar no `.md` (RF-03).

Todos levantados na revisão crítica (Codex CLI) como detalhes que, se não decididos agora,
forçariam retrabalho no meio da implementação — registrados aqui para não se perderem antes do
`/reversa-to-do`.

## 11. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório)

## 12. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-12 | Versão inicial gerada por `/reversa-plan` | reversa |
| 2026-08-12 | Revisão crítica via `/brainstorming-multiagent` (Codex CLI + Nemotron/OpenCode): D-06 revertido para container/imagem dedicados com limites de recursos; D-03/D-07 corrigidos (contradição de idempotência); D-09/D-10/D-11 adicionados (prontidão de arquivo, lease de proteção, esclarecimento de isolamento por tenant); passo 0 bloqueante de benchmark do host adicionado ao plano de migração; seção 9 (riscos) reescrita | reversa |
