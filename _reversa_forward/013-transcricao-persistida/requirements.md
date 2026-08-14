# Requirements: Transcrição persistida (F1 — Épico 2: Qualidade do Atendimento)

> Identificador: `013-transcricao-persistida`
> Data: `2026-08-12`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Cria o consumidor que falta na cadeia áudio → STT → transcrição: consome os canais de áudio já
capturados e separados pelo B2BUA (`tx`=atendente, `rx`=cliente), transcreve de forma assíncrona
e pós-chamada via Whisper.cpp local (sem GPU), persiste os segmentos em `Transcript` e publica um
`.md` consolidado no SMB, ao lado do `stereo.mp3` já existente da mesma chamada. É a primeira
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
| `_reversa_sdd/addenda/011-smb-audio-backup.md` | `tx.mp3`/`rx.mp3` são as fontes mono; `stereo.mp3` é derivado via `generate_stereo()` e publicado no SMB em `{tenant}/{YYYY-MM-DD}/{prefix}-{call_id[:6]}-{caller}-{callee}.mp3` (`build_remote_directory`/`build_remote_name`, `src/workers/smb_sync.py`); indisponibilidade do SMB nunca pode interromper a gravação local — mesmo princípio se aplica aqui para a transcrição | 🟢 |
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
   partir dos arquivos `tx.mp3`/`rx.mp3` já persistidos localmente em disco** (mesma fonte que a
   feature `011-smb-audio-backup` usa para gerar o `stereo.mp3`) — não consome os eventos de
   chunk de áudio ao vivo publicados por `AudioIngestor` durante a chamada. O motor Deepgram fica
   reservado para a análise em tempo real (F6, fora de escopo) e não deve ser usado aqui. 🟢
   - Tipo: nova
   - Resolvida em `/reversa-clarify`, ver seção 9
3. **RN-03:** O arquivo `.md` da transcrição usa a mesma base de nome e o mesmo diretório do
   `stereo.mp3` já publicado no SMB pela feature `011-smb-audio-backup`
   (`{tenant}/{YYYY-MM-DD}/{prefix}-{call_id[:6]}-{caller}-{callee}`), trocando apenas a
   extensão. Decisão confirmada com o usuário nesta sessão (o pipeline não usa `.mp4` em nenhum
   ponto — o áudio real persistido é `stereo.mp3`). 🟢
   - Tipo: nova
4. **RN-04:** Falha na transcrição ou na publicação do `.md` nunca pode interromper ou atrasar a
   gravação de áudio nem o backup SMB do `.mp3` — mesmo princípio best-effort já aplicado ao
   backup SMB. 🟢
   - Origem no legado: `_reversa_sdd/addenda/011-smb-audio-backup.md#Impactos que devem
     permanecer visíveis`
   - Tipo: nova aplicação de regra já confirmada
5. **RN-05:** A transcrição deve ocorrer enquanto `tx.mp3`/`rx.mp3` ainda existem localmente em
   disco — antes do ciclo de limpeza (`audio_cleanup`) removê-los. O disparo deve acontecer logo
   após o fim da chamada, na mesma janela em que o backup SMB (feature `011`) já é disparado, não
   em horário arbitrário posterior. 🟢
   - Tipo: nova
   - Resolvida em `/reversa-clarify`, ver seção 9

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|---------------------|-------------|
| RF-01 | Transcrever os canais `tx`/`rx` de uma chamada a partir dos arquivos `tx.mp3`/`rx.mp3` já persistidos localmente (RN-02), dividindo cada arquivo em janelas/segmentos para o `WhisperCppSTT` (Strategy já implementado) processar, sem depender de GPU. | Must | Uma chamada real gerada em produção tem seus dois canais transcritos sem erro, com texto não vazio para áudio com fala. | 🟢 |
| RF-02 | Persistir cada segmento transcrito diretamente em `Transcript` (Postgres), em transação única por chamada, com `speaker` mapeado para "atendente" (`tx`) / "cliente" (`rx`) conforme RN-01, usando o atributo `extra_metadata` do model (não `metadata`, reservado pelo SQLAlchemy declarative). Não reutiliza a indireção via Redis List de `TranscriptPersister.buffer_transcript`/`flush_batch` — sem valor de proteção real num processamento em lote sobre arquivo já em disco (RN-02), e o `LRANGE`/commit/`DEL` daquele fluxo tem janela real de duplicação em retry. | Must | Consulta ao banco após uma chamada real mostra linhas `Transcript` com `channel`/`speaker`/`text`/`extra_metadata` preenchidos e `call_id` correto, sem passar por `transcripts:batch:*` no Redis. | 🟢 |
| RF-03 | Gerar um `.md` consolidado com a transcrição completa da chamada — cada segmento rotulado por falante (atendente/cliente) com timestamp de início/fim e confidence, no mesmo espírito incremental/timestampado da skill `audio-transcript-long` já presente no projeto (`.agents/skills/audio-transcript-long/`) — e publicá-lo no SMB, mesma base de nome e diretório do `stereo.mp3` correspondente (RN-03). | Must | Após uma chamada real com backup SMB concluído, existe um `.md` no mesmo diretório do `.mp3`, com nome-base idêntico, e cada linha de fala traz falante + timestamp + confidence. | 🟢 |
| RF-04 | Disparar a transcrição de forma assíncrona, sem bloquear ou atrasar a gravação, o upload ou o backup SMB do áudio (RN-04), e antes do ciclo de limpeza remover `tx.mp3`/`rx.mp3` (RN-05). | Must | Uma falha simulada no Whisper.cpp não impede a gravação nem o backup SMB de completarem normalmente; a transcrição roda antes da janela de retenção/limpeza expirar. | 🟢 |
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
  Dado que uma chamada real foi gravada e seu stereo.mp3 já foi publicado no SMB
  Quando o processamento assíncrono de transcrição é executado para essa chamada
  Então um arquivo .md com o mesmo nome-base do stereo.mp3 aparece no mesmo diretório do SMB
  E o conteúdo do .md distingue claramente as falas do atendente e do cliente

Cenário: Falha no Whisper.cpp não impacta a gravação nem o backup de áudio
  Dado que o binário whisper-cpp está indisponível ou falha durante o processamento
  Quando o job de transcrição é executado para uma chamada
  Então a gravação e o backup SMB do .mp3 dessa chamada continuam completando normalmente
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
