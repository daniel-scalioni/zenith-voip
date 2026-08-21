# Requirements: Transcrição persistida (F1 — Épico 2: Qualidade do Atendimento)

> Identificador: `013-transcricao-persistida`
> Data: `2026-08-12`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Cria o consumidor que falta na cadeia áudio → STT → transcrição: consome os canais de áudio já
capturados e separados pelo B2BUA (`tx`=atendente, `rx`=cliente), transcreve de forma assíncrona
e pós-chamada via Whisper.cpp local (sem GPU), persiste os segmentos em `Transcript` e publica um
`.md` consolidado no SMB, ao lado do `stereo.wav` já existente da mesma chamada. É a primeira
feature do Épico 2 (Qualidade do Atendimento) e não faz nenhuma análise de qualidade — sentimento,
auditoria de POP e anomalia ficam para F3-F5 (`_reversa_sdd/ai/epico-2-qualidade-atendimento.md`).

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/architecture.md#Débitos técnicos` (TD02/TD03) | `analyze_sentiment()`/`audit_procedure()` são stubs em `post_call.py` — fora de escopo de F1, mas confirma que o domínio de qualidade nunca foi conectado | 🟢 |
| `_reversa_sdd/domain.md#R43` | "Frame estéreo é dividido por índice: pares = `tx` (agente), ímpares = `rx` (cliente)" — base da diferenciação atendente/cliente desta feature | 🟢 |
| `_reversa_sdd/domain.md#Glossário` | `Transcript`: "Segmento de texto transcrito do áudio de uma chamada, com canal (tx/rx), speaker, confidence e timestamps" — entidade já modelada, nunca populada | 🟢 |
| `_reversa_sdd/code-analysis.md#3-audio` | `AudioIngestor` faz de-interleaving PCM16 estéreo e publica um evento por canal no Redis Stream — não há consumidor desses eventos hoje | 🟢 |
| `_reversa_sdd/code-analysis.md#8-services` | Strategy Pattern (`STTStrategy`) já implementa `WhisperCppSTT` e `AutoFallbackSTT` (Deepgram→Whisper); nenhum dos dois é chamado em produção | 🟢 |
| `_reversa_sdd/code-analysis.md#10-workers` | Buffer de transcrições no Redis com flush batch (`TranscriptPersister`) já existe, nunca é chamado | 🟢 |
| `_reversa_forward/014-captura-wav-16k/interfaces/recording-audio-files.md` | `tx.wav`/`rx.wav` são as fontes mono PCM16 16 kHz; `stereo.wav` é derivado e publicado no SMB em `{tenant}/{YYYY-MM-DD}/{prefix}-{call_id[:6]}-{caller}-{callee}.wav`; o lifecycle compartilhado protege os consumidores contra cleanup concorrente | 🟢 |
| `_reversa_forward/001-ai-audio-hub/requirements.md#3` | Persona "Gestor / Auditor: garantir a qualidade do atendimento" já estabelecida no PRD original | 🟢 |
| `.agents/skills/audio-transcript-long/SKILL.md` | Skill do projeto (não faz parte da extração reversa, é artefato do harness) para transcrição de áudio longo: chunking via `ffmpeg`, escrita incremental com timestamp por segmento, fallback de OOM. Referência de formato para o `.md` desta feature (RF-03) — não necessariamente reaproveitada linha a linha, já que o motor lá é `faster-whisper`/`openai-whisper` e o formato de saída é `.srt`, enquanto aqui o motor é `WhisperCppSTT` (já decidido) e a saída é `.md` | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|----------------|
| Equipe de Qualidade (analista) | Ler a transcrição de uma chamada para avaliar o atendimento | Abre o `.md` no mesmo diretório SMB do áudio (`{tenant}/{YYYY-MM-DD}/`), sem precisar rodar STT manualmente ou ouvir o áudio inteiro |
| Gestor / Auditor | Garantir a qualidade do atendimento (persona já registrada em `001-ai-audio-hub`) | Consumirá relatórios de sentimento/auditoria nas features seguintes (F3-F5); esta feature entrega a base de texto que sustenta esses relatórios |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** A diferenciação entre atendente e cliente usa exclusivamente o canal de áudio já
   separado fisicamente pelo B2BUA (`tx`=atendente, `rx`=cliente) — sem diarização de IA
   adicional. 🟢
   - Origem no legado: `_reversa_sdd/domain.md#R43`
   - Tipo: nova aplicação de regra já confirmada
2. **RN-02:** A transcrição desta feature é assíncrona e pós-chamada, processada em **lote a
   partir dos arquivos `tx.wav`/`rx.wav` PCM16 mono 16 kHz já persistidos localmente em disco**
   (mesma fonte que o backup SMB usa para gerar o `stereo.wav`) — não consome os eventos de
   chunk de áudio ao vivo publicados por `AudioIngestor` durante a chamada. O motor Deepgram fica
   reservado para a análise em tempo real (F6, fora de escopo) e não deve ser usado aqui. 🟢
   - Tipo: nova
   - Resolvida em `/reversa-clarify`, ver seção 9
3. **RN-03:** O arquivo `.md` da transcrição usa a mesma base de nome e o mesmo diretório do
   `stereo.wav` já publicado no SMB
   (`{tenant}/{YYYY-MM-DD}/{prefix}-{call_id[:6]}-{caller}-{callee}`), trocando apenas a
   extensão. O contrato WAV 16 kHz foi entregue e validado pela feature 014. 🟢
   - Tipo: nova
4. **RN-04:** Falha na transcrição ou na publicação do `.md` nunca pode interromper ou atrasar a
   gravação de áudio nem o backup SMB do `.wav` — mesmo princípio best-effort já aplicado ao
   backup SMB. 🟢
   - Origem no legado: `_reversa_sdd/addenda/011-smb-audio-backup.md#Impactos que devem
     permanecer visíveis`
   - Tipo: nova aplicação de regra já confirmada
5. **RN-05:** A transcrição deve ocorrer enquanto `tx.wav`/`rx.wav` ainda existem localmente em
   disco — antes do ciclo de limpeza (`audio_cleanup`) removê-los. O disparo deve acontecer logo
   após o fim da chamada, na mesma janela em que o backup SMB (feature `011`) já é disparado, não
   em horário arbitrário posterior. 🟢
   - Tipo: nova
   - Resolvida em `/reversa-clarify`, ver seção 9
6. **RN-06:** O worker só inicia quando os dois canais finais `tx.wav` e `rx.wav` existem; canal
   ausente, vazio ou arquivo `.tmp` mantém a chamada pendente. Os dois canais usam tempo relativo
   ao início da chamada (offset zero) e os segmentos somam o offset da janela para permitir a
   intercalação temporal. 🟢
7. **RN-07:** Durante o processamento o worker mantém lease `transcription` exclusivo e renovado.
   O marcador `.consumed-transcription` só é gravado depois de banco e `.md` SMB concluírem; uma
   falha deixa a chamada elegível para retry no próximo ciclo. 🟢

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|---------------------|-------------|
| RF-01 | Transcrever os canais `tx`/`rx` a partir de `tx.wav`/`rx.wav` PCM16 mono 16 kHz (RN-02), dividindo cada arquivo em janelas sem reamostragem antes de chamar `WhisperCppSTT`, sem depender de GPU. O adapter deve localizar o binário no `$PATH`, ler o JSON sidecar completo gerado por `-ojf` e obter confidence pela média de `tokens[].p`, com `exp(avg_logprob)` como fallback, sempre em `[0,1]`. | Must | Uma chamada real tem os dois canais transcritos, o JSON é lido corretamente e toda confidence está em `[0,1]`. | 🟢 |
| RF-02 | Persistir cada segmento transcrito diretamente em `Transcript` (Postgres), em transação única por chamada, com `speaker` mapeado para "atendente" (`tx`) / "cliente" (`rx`) conforme RN-01, usando o atributo `extra_metadata` do model (não `metadata`, reservado pelo SQLAlchemy declarative). Não reutiliza a indireção via Redis List de `TranscriptPersister.buffer_transcript`/`flush_batch` — sem valor de proteção real num processamento em lote sobre arquivo já em disco (RN-02), e o `LRANGE`/commit/`DEL` daquele fluxo tem janela real de duplicação em retry. | Must | Consulta ao banco após uma chamada real mostra linhas `Transcript` com `channel`/`speaker`/`text`/`extra_metadata` preenchidos e `call_id` correto, sem passar por `transcripts:batch:*` no Redis. | 🟢 |
| RF-03 | Gerar um `.md` consolidado com segmentos rotulados, timestamps relativos e confidence, e publicá-lo no SMB com a mesma base/diretório do `stereo.wav` correspondente (RN-03). | Must | Existe um `.md` ao lado do `.wav`, com nome-base idêntico e cada fala traz falante + timestamp + confidence. | 🟢 |
| RF-04 | Executar em worker/fila exclusivos, com concorrência 1, timeout por chamada e retry por polling, sem bloquear gravação/upload/backup; participar do lifecycle conforme RN-07. | Must | Falhas de Whisper/SMB não afetam outros workers, lease impede cleanup durante STT e chamadas incompletas/falhas voltam a ser elegíveis. | 🟢 |
| RF-05 | Reprocessar uma chamada já transcrita não deve duplicar segmentos no banco: `Transcript` é substituído de forma idempotente por `call_id` (delete+insert ou upsert transacional) e o `.md` final fica consistente com o último reprocessamento. | Should | Executar o job de transcrição duas vezes para o mesmo `call_id` resulta no mesmo conjunto de segmentos (sem duplicatas) e no mesmo `.md` final. | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|------------------------------|-------------|
| Desempenho | Deve rodar em CPU, sem exigir GPU; tempo de processamento pode ser maior que tempo real, já que é assíncrono/pós-chamada. | Decisão do usuário nesta sessão (Whisper.cpp local em vez de Voxtral/vLLM, que exigiria GPU) | 🟢 |
| Segurança / LGPD | O texto transcrito pode conter dados sensíveis (CPF, RG) faladas na ligação; processamento deve permanecer local, nunca sair para serviço de nuvem nesta etapa. | `_reversa_sdd/architecture.md#adr-003` (dados sensíveis processados exclusivamente por LLM/processamento local) | 🟢 |
| Observabilidade | Falhas de transcrição devem gerar log estruturado (nunca `print()`) identificável por `call_id`, para permitir auditoria de chamadas sem `.md` gerado. | Convenção já estabelecida no projeto (`AGENTS.md#Anti-Padrões`) | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Transcrição de chamada real gera .md ao lado do áudio no SMB
  Dado que uma chamada real foi gravada e seu stereo.wav já foi publicado no SMB
  Quando o processamento assíncrono de transcrição é executado para essa chamada
  Então um arquivo .md com o mesmo nome-base do stereo.wav aparece no mesmo diretório do SMB
  E o conteúdo do .md distingue claramente as falas do atendente e do cliente

Cenário: Falha no Whisper.cpp não impacta a gravação nem o backup de áudio
  Dado que o binário whisper-cpp está indisponível ou falha durante o processamento
  Quando o job de transcrição é executado para uma chamada
  Então a gravação e o backup SMB do .wav dessa chamada continuam completando normalmente
  E a falha de transcrição é registrada em log estruturado, sem interromper outros jobs

Cenário: Reprocessar uma chamada já transcrita não duplica dados
  Dado que uma chamada já tem seus segmentos persistidos em Transcript e seu .md publicado no SMB
  Quando o job de transcrição é executado novamente para o mesmo call_id
  Então o conjunto de segmentos em Transcript permanece o mesmo, sem duplicatas
  E o .md publicado no SMB permanece consistente com o conteúdo anterior
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|-----------------|
| RF-01, RF-02, RF-03, RF-04 | Must | São o núcleo da feature — sem eles não existe transcrição persistida nem entrega do `.md` |
| RF-05 (idempotência) | Should | Importante para reprocessamento seguro, mas a feature entrega valor real mesmo sem isso no primeiro corte |
| RNF de segurança/LGPD | Must | Alinhado a princípio já registrado do projeto (ADR-003); não é opcional dado o tipo de dado tratado |

## 9. Esclarecimentos

### Sessão 2026-08-12

> Registro histórico: as respostas abaixo usavam MP3 antes da feature 014. A decisão posterior do
> usuário substituiu esse formato por `tx.wav`/`rx.wav` e `stereo.wav` PCM16 16 kHz; RN-02/RF-01
> e o roadmap atual são o contrato vigente.

- **Q:** Fonte do áudio para transcrição — chunks ao vivo do `AudioIngestor` (Redis) ou arquivos
  `tx.mp3`/`rx.mp3` já persistidos localmente após o fim da chamada?
  **R:** Arquivos `tx.mp3`/`rx.mp3` já persistidos localmente em disco (mesma fonte que a feature
  `011-smb-audio-backup` usa para gerar `stereo.mp3`), que depois são apagados pelo ciclo de
  limpeza — ver RN-02 e RN-05 (nova regra criada a partir desta resposta, sobre a janela de
  disparo antes da limpeza remover os arquivos).
- **Q:** Formato exato do `.md` — só texto consolidado, ou texto + metadados por linha
  (timestamp, confidence)?
  **R:** Texto + metadados por linha, conforme o padrão já usado pela skill do projeto
  `audio-transcript-long` (escrita incremental com timestamp por segmento) — ver RF-03 e a nova
  entrada de contexto na seção 2 citando essa skill.
- **Q:** Bug latente em `TranscriptPersister.flush_batch` (`metadata=` não bate com
  `extra_metadata` do model) — corrigir dentro do escopo de F1 ou registrar como GAP separado?
  **R:** Corrigir dentro do escopo de F1. Consulta a `/brainstorming-multiagent` (Codex CLI +
  DeepSeek via OpenCode, lentes de robustez/idempotência e de simplicidade/menor-avanço)
  convergiu numa recomendação mais ampla do que o fix de uma linha: não reaproveitar a indireção
  via Redis List de `buffer_transcript`/`flush_batch` — o fluxo `LRANGE → commit → DEL` não
  protege nada num processamento em lote sobre arquivo já em disco (o próprio `tx.mp3`/`rx.mp3`
  já é o buffer durável) e tem janela real de duplicação em retry entre o commit e o `DEL`.
  Ambos os modelos convergiram em persistência direta e transacional no Postgres, substituição
  idempotente por `call_id` (delete+insert ou upsert) — ver RF-02 e RF-05 atualizados. Redis
  segue como infraestrutura de fila/retry do `arq`, não como staging de transcript.

## 10. Lacunas

Nenhuma lacuna aberta no momento. Todos os pontos levantados na versão inicial foram resolvidos
em `/reversa-clarify` (ver seção 9).

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-12 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-08-12 | 3 dúvidas resolvidas via `/reversa-clarify` (fonte do áudio, formato do `.md`, correção do `TranscriptPersister`); RN-02/RN-05 e RF-01/RF-02/RF-03/RF-04/RF-05 atualizados | reversa |
| 2026-08-18 | Contrato atualizado após fechamento da 014: WAV PCM16 16 kHz, lifecycle `transcription`, prontidão dos dois canais, timestamps e adapter whisper.cpp completo | reversa-coding |
