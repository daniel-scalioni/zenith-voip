# Roadmap: Transcrição persistida (F1 — Épico 2: Qualidade do Atendimento)

> Identificador: `013-transcricao-persistida`
> Data: `2026-08-12`
> Requirements: `_reversa_forward/013-transcricao-persistida/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Um novo worker ARQ (`arq-transcript`, fila exclusiva `zenith:transcript`) roda em cron polling
sobre `RECORDINGS_PATH/*/*` — mesmo padrão já usado por `run_smb_sync` (feature `011`) — buscando
pares `tx.wav`/`rx.wav` PCM16 mono 16 kHz ainda não transcritos. O worker consulta o transfer log
**já produzido pelo SMB** para obter o nome remoto exato da chamada e checa idempotência por
linhas `Transcript`, Markdown e marcador terminal; não cria um segundo log. Para cada par,
divide os arquivos em janelas via `ffmpeg` (já presente na imagem), alimenta cada janela ao
`WhisperCppSTT` (corrigindo o bug de detecção do binário encontrado nesta etapa), grava os
segmentos diretamente em `Transcript` (Postgres, transação única, substituição idempotente por
`call_id`, sem a indireção via Redis List de `TranscriptPersister`), e gera um `.md` consolidado
publicado no SMB com o mesmo nome-base e diretório do `stereo.wav` correspondente, reaproveitando
as funções de nomeação/conexão já existentes em `src/workers/smb_sync.py`. Nenhuma análise de
qualidade (sentimento, auditoria, anomalia) faz parte desta feature.

## 2. Princípios aplicados

`.reversa/principles.md` não existe neste projeto — nenhum princípio formal registrado ainda.
N/a.

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|----------------------------|-------------|
| D-01 | Descoberta por cron polling sobre `RECORDINGS_PATH/*/*` verificando `tx.wav`+`rx.wav` finais, não vazios e sem `.tmp`, em vez de hook síncrono no `CHANNEL_HANGUP`. | Mesmo padrão validado por `smb_sync`; mantém telefonia fora do worker de qualidade. | Hook direto no hangup | 🟢 |
| D-02 | Fila e worker exclusivos: `arq-transcript` / `zenith:transcript`, mesmo princípio de isolamento já aplicado a `arq-uploader`/`arq-cleanup`/`arq-smb-sync`. | `_reversa_forward/011-smb-audio-backup/requirements.md#RF-13` ("Isolar os workers ARQ operacionais em filas exclusivas") | Reaproveitar `zenith:smb-sync` ou `zenith:audio-upload` (rejeitada: mistura responsabilidades, um job lento de STT atrasaria upload/backup) | 🟢 |
| D-03 | O polling obtém ownership/diretório/nome do WAV pelo item `done` da própria chamada no `smb_transfer_log.json` e só pula quando `Transcript` existe **e** o `.md` exato aparece em uma única listagem remota, sem baixar o arquivo. | O transfer log já é a fonte de verdade do backup e elimina ambiguidade entre chamadas colidentes; banco+SMB provam conclusão. | Inferir ownership pela presença de nomes candidatos ou baixar o arquivo | 🟢 |
| D-04 | Dividir os WAV 16 kHz em janelas via `ffmpeg`, sem reamostragem; ambos os canais começam em offset zero e cada segmento soma a duração real dos chunks anteriores medida pelos frames WAV. | Limita memória e preserva alinhamento mesmo quando o muxer corta alguns milissegundos depois da janela nominal. | `index * duração configurada` ou arquivo inteiro | 🟢 |
| D-05 | Corrigir `WhisperCppSTT`: localizar via `shutil.which`, ler o sidecar `<input>.json` produzido por `-ojf`, validar o payload, interpretar offsets em milissegundos e obter confidence média dos tokens `p` (fallback `exp(avg_logprob)`), limitada a `[0,1]`. O subprocesso assíncrono é encerrado em timeout/cancelamento. | O adapter antigo procurava caminho relativo, lia stdout e expunha log-prob negativo. | Manter contrato quebrado | 🟢 |
| D-06 | **Imagem/container dedicados** (`zenith-arq-transcript`, `Dockerfile.transcript`) com whisper.cpp v1.8.6/modelo base multilíngue verificado, limite de 1,5 CPU/768 MiB, um thread e `max_jobs=1`. | Benchmark real: 30 s de WAV consumiram 107,887 s wall/107,310 s CPU e pico de 294.146.048 bytes com um thread; quatro threads sob cap pioraram para 126,708 s wall. Os limites preservam 4,5 das 6 vCPUs e têm >2,5× a memória observada. | Imagem da API ou execução sem limites | 🟢 |
| D-07 | Persistência **do banco** idempotente via `pg_advisory_xact_lock(hashtext(call_id))` + delete+insert numa única transação por chamada — protege contra duas execuções concorrentes do mesmo `call_id` (ex.: dois disparos de polling sobrepostos). **Sem** reutilizar `TranscriptPersister.buffer_transcript`/`flush_batch` (`src/workers/transcript_persist.py`). Distinto da checagem de descoberta (D-03): esta é sobre concorrência de escrita, não sobre "já processei essa chamada?". | Decisão tomada em `/reversa-clarify` após consulta `/brainstorming-multiagent` (Codex CLI + DeepSeek/OpenCode, convergentes): o fluxo `LRANGE → commit → DEL` do `TranscriptPersister` não protege nada num processamento em lote sobre arquivo já em disco e tem janela real de duplicação em retry. O advisory lock foi acrescentado na revisão crítica seguinte (Codex CLI) para cobrir concorrência entre execuções, que o `delete+insert` sozinho não cobre | Corrigir só o bug `metadata`→`extra_metadata` e manter a indireção via Redis List (rejeitada pelas duas lentes consultadas — ver `requirements.md#9`); `delete+insert` sem lock (rejeitada na revisão crítica: duas execuções concorrentes do mesmo `call_id` podem intercalar delete/insert e produzir estado inconsistente) | 🟢 |
| D-08 | Reaproveitar `build_remote_directory`, `build_remote_name(..., extension="md")` e `SMBBackupStrategy`; o `.md` usa a base do `.wav`. | Evita duplicar client e nomenclatura SMB. | Client próprio | 🟢 |
| D-09 | **Prontidão**: os dois WAV finais devem existir, ter tamanho maior que o cabeçalho e nenhum `.tmp` relacionado pode existir. | Reaproveita o rename atômico entregue pela 014. | Timer de estabilidade próprio | 🟢 |
| D-10 | **Lifecycle**: adicionar `transcription` aos estágios, adquirir/renovar lease cross-stage e marcar `consumed-transcription` apenas depois de banco+SMB. O cleanup preserva backlog vencido em capacidade normal, mas sob pressão abaixo da margem de retomada aplica TTL para proteger novas gravações. | Impede cleanup concorrente sem permitir que falha permanente do consumidor esgote o tmpfs. | Retenção infinita ou TTL cego | 🟢 |
| D-12 | Canal ausente/vazio mantém pending; timeout por chamada cancela o processamento e o polling retenta. A concorrência do worker é 1. | Fecha caminhos operacionais sem bloquear telefonia. | Persistência parcial | 🟢 |
| D-11 | **Isolamento por tenant já é estrutural, não precisa de coluna nova**: `Transcript` é `TenantBase` (`src/database/models.py:13,161`) — vive fisicamente no schema `tenant_<id>`, schema-per-tenant. Colisão de `call_id` entre tenants é impossível por construção (schemas distintos = tabelas distintas). O advisory lock (D-07) é escopado à sessão/schema do tenant conectado. | Revisão crítica (Codex CLI) levantou risco de `call_id` não ser tenant-aware; confirmado por leitura direta do código que a arquitetura de multitenancy já garante isso — registrado aqui como esclarecimento, não como decisão nova | n/a — não é uma escolha, é confirmação de garantia já existente | 🟢 |

## 4. Premissas

Nenhuma — `requirements.md` não tem marcador `[DÚVIDA]` pendente (todos resolvidos em
`/reversa-clarify`, ver `requirements.md#9`).

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-------------------|--------|
| Worker de transcrição em lote (novo) | `_reversa_sdd/code-analysis.md#10-workers` | componente-novo | Novo módulo `src/workers/transcript_batch.py`: cron polling, chunking, chama `WhisperCppSTT`, persiste `Transcript`, gera/publica `.md` |
| `WhisperCppSTT` (`src/services/stt_whisper.py`) | `_reversa_sdd/code-analysis.md#8-services` | contrato-alterado | Corrige descoberta, sidecar JSON e confidence (D-05); primeira execução real em produção |
| `TranscriptPersister` (`src/workers/transcript_persist.py`) | `_reversa_sdd/code-analysis.md#10-workers` | componente-extinto (do caminho de execução) | Deixa de ser chamado por esta feature (D-07); arquivo permanece em disco, decisão de removê-lo ou não fica para o `/reversa-to-do` |
| Imagem dedicada (`Dockerfile.transcript`) | `_reversa_sdd/infra/deployment/design.md` | componente-novo | Build multi-stage do `whisper-cli` e modelo base multilíngue, sem aumentar a imagem da API (D-06) |
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
| **Contenção de CPU no host**: FreeSWITCH + Ollama + whisper.cpp competem pelas 6 vCPUs. | alto | médio | Container limitado a 1,5 CPU/768 MiB, um thread e `max_jobs=1`; chamada real deve confirmar jitter antes do aceite final. |
| Build do binário `whisper-cpp` + modelo aumenta o tempo/tamanho da imagem Docker — mitigado por imagem separada (D-06), mas o binário ainda precisa ser buildado/baixado. | médio | médio | Cache de camada Docker na imagem dedicada `zenith-transcript` |
| Chamada excepcionalmente longa estoura memória mesmo com chunking. | alto | baixo | Fallback recursivo de corte pela metade, mesmo padrão já usado pela skill `audio-transcript-long`; `deploy.resources.limits` de memória (D-06) garante falha contida (OOM do container) em vez de derrubar o host |
| Job de transcrição não termina antes do cleanup remover `tx.wav`/`rx.wav`. | alto | médio | Lease `transcription` renovado + consumidor obrigatório (D-10) |
| Descoberta processa WAV ainda sendo escrito. | alto | baixo | Rename atômico, par completo e ausência de `.tmp` (D-09) |
| Duas execuções concorrentes do mesmo `call_id` corrompem a escrita no banco. | médio | baixo | `pg_advisory_xact_lock` + delete/insert transacional (D-07) |
| Dados sensíveis (CPF, RG) presentes no `.md` e no banco sem controle adicional específico. | alto | baixo | Mesma política já aplicada ao `stereo.wav` no SMB |

## 10. Decisões operacionais fechadas em 2026-08-18

- Janela de 30 s, 1,5 CPU, 768 MiB, um thread e timeout de chamada de 3.600 s.
- Retry ocorre no polling seguinte; subprocesso é morto em timeout/cancelamento.
- Um canal ausente/vazio mantém pending e não produz persistência parcial.
- `tx` e `rx` começam em zero; cada segmento soma o offset da sua janela.

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
| 2026-08-18 | Benchmark real e decisões operacionais fechados; contrato alinhado à 014/WAV e ao CLI oficial v1.8.6 | reversa-coding |
