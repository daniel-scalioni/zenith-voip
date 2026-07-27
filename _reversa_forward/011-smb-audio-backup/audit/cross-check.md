# Cross-Check: SMB Audio Backup para Auditoria

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`
> Artefatos analisados:
> - `_reversa_forward/011-smb-audio-backup/requirements.md`
> - `_reversa_forward/011-smb-audio-backup/roadmap.md`
> - `_reversa_forward/011-smb-audio-backup/actions.md`
> - Apoio: `data-delta.md`, `investigation.md`, `onboarding.md`, `interfaces/smb.md`
> - Legado: `_reversa_sdd/domain.md`, `_reversa_sdd/architecture.md`, `src/`, `docker-compose.app.yml`

**Este relatório não alterou nenhum dos artefatos auditados.** A única escrita foi este arquivo.

## Resumo

| Severidade | Quantidade |
|------------|-----------|
| CRITICAL | 1 |
| HIGH | 5 |
| MEDIUM | 3 |
| LOW | 2 |
| **Total** | **11** |

## Findings

| ID | Severidade | Eixo | Descrição | Onde está |
|----|-----------|------|-----------|-----------|
| A001 | CRITICAL | Coerência com o legado | Todas as citações da extração apontam para `specs/`, que **não** é a pasta da extração reversa — os artefatos estão em `_reversa_sdd/`. `specs/` é pasta pré-existente do projeto (CSV de ramais, pcaps, `deploy.md`). T001 e T026 gravariam arquivos novos dentro dela | `requirements.md#2`, `roadmap.md#5`, `actions.md` T001/T026 |
| A002 | HIGH | Consistência | Critério de aceite exige "copiado em < 30s após gravação", mas a decisão de arquitetura define varredura por cron de 5 min — a latência ponta a ponta é de até ~5 min + tempo de cópia, não 30s | `requirements.md` RF-01 / RNF Desempenho / Gherkin cenário 1 vs. `roadmap.md#D-01` e `actions.md` T010 |
| A003 | HIGH | Cobertura | RF-07 (Must) e o cenário Gherkin "Auditoria acessa arquivos com permissão READ-ONLY" não têm nenhuma ação em `actions.md`; a ACL só aparece como passo em prosa no plano de migração | `requirements.md` RF-07, `roadmap.md#8` passo 1, ausente em `actions.md` |
| A004 | HIGH | Sanidade / legado | Corrida de escrita não tratada: `_convert_to_mp3` (`src/workers/audio_uploader.py:14`) grava o `.mp3` via ffmpeg de forma incremental. T017 varre `*.mp3` sem verificar estabilidade do arquivo, podendo copiar arquivo truncado — e o checksum de T015 **não** detecta, porque compara o destino com a mesma origem truncada | `actions.md` T015/T017, `interfaces/smb.md#Integridade` |
| A005 | HIGH | Cobertura | O caminho `uploaded_raw_only` de `upload_audio_chunk` deixa apenas `{channel}.raw` quando o ffmpeg falha. T017 varre somente `*.mp3`, então esses áudios nunca chegam ao share de auditoria e nada sinaliza a ausência | `src/workers/audio_uploader.py:44`, `actions.md` T017 |
| A006 | HIGH | Coerência com o legado | A escolha de manter credenciais em `.env` é justificada por "padrão já aplicado no projeto para S3", e `investigation.md` afirma que existe "upload assíncrono a S3". Não há S3 no código: `grep -rn boto3 src/` vazio e `requirements.txt` sem biblioteca S3. Justificativa sem lastro | `requirements.md#6` RNF Segurança, `roadmap.md#D-07`, `investigation.md` |
| A007 | MEDIUM | Coerência com o legado | Regras 🟢 de `_reversa_sdd/domain.md` contradizem as premissas da feature e o código atual: R28 "retenção 90 dias" vs. ~1h real (`AUDIO_RETENTION_DAYS=0.0417`), R29 "cleanup diário 03:00" vs. cron a cada 15 min, R30/R31 sobre S3 inexistente. T005 altera retenção sem reconciliar R28 | `_reversa_sdd/domain.md:103-106`, `actions.md` T005 |
| A008 | MEDIUM | Sanidade do actions | T005 e T021 estão ambas marcadas `[//]` e têm o mesmo arquivo alvo `docker-compose.app.yml`. Não há corrida real (T021 depende de T005), mas o marcador viola a convenção do template ("tarefas `[//]` não compartilham arquivo alvo") | `actions.md` T005, T021 |
| A009 | MEDIUM | Sanidade do actions | T026 descreve edição de dois arquivos (`design.md` e `gaps.md`) mas declara apenas um na coluna de arquivo alvo, o que quebra a rastreabilidade de impacto | `actions.md` T026 |
| A010 | LOW | Coerência com o legado | O gap 🔴 registrado em `_reversa_sdd/domain.md:121` (`_detect_channel()` retorna "tx" hardcoded, "canal RX nunca identificado") não existe mais no código — o ingestor usa `_split_stereo_frame` e produz tx e rx. Documentação desatualizada, sem impacto nesta feature | `_reversa_sdd/domain.md:121` vs. `src/audio/ingestor.py:51-56` |
| A011 | LOW | Sanidade do actions | T007–T009 escrevem testes de funções criadas só em T011–T014, então o gate bloqueante `pytest tests/ -v` (CLAUDE.md#Quality Gates) fica vermelho entre T007 e T017. Esperado em TDD, mas convém estar explícito para não parecer regressão | `actions.md` T007–T009 |

## Detalhamento dos CRITICAL e HIGH

### A001 — Caminho da extração aponta para pasta errada (CRITICAL)

A causa raiz está em `.reversa/state.json`, campo `output_folder: "specs"`. Os skills do pipeline resolvem as citações por esse campo, mas a extração reversa deste projeto está em `_reversa_sdd/` (confirmado: `_reversa_sdd/architecture.md`, `domain.md`, `gaps.md`, `workers/audio-upload/design.md` existem; nenhum equivalente existe sob `specs/`).

Dois impactos distintos:

1. **Rastreabilidade quebrada:** todas as citações de `requirements.md#2` e `roadmap.md#5` apontam para arquivos inexistentes, então nenhuma decisão da feature está de fato ancorada no legado de forma verificável.
2. **Risco de escrita indevida:** T001 criaria `specs/workers/smb-backup/design.md` e T026 editaria `specs/gaps.md` — ou seja, gravaria dentro de uma pasta pré-existente do projeto, que hoje guarda `export_extensions.csv`, pcaps e `deploy.md`. Isso contraria a regra não-negociável do `CLAUDE.md` ("O Reversa escreve **apenas** em `.reversa/` e `_reversa_sdd/`").

Direção sugerida: corrigir `output_folder` em `.reversa/state.json` para `_reversa_sdd` e reescrever as citações dos artefatos. A correção dos artefatos não é feita por este skill — use edição manual ou `/reversa-clarify`.

### A002 — Critério de aceite de latência incompatível com o modelo de varredura (HIGH)

`requirements.md` afirma três vezes que o arquivo estará no SMB em menos de 30 segundos (RF-01, RNF de desempenho e o primeiro cenário Gherkin). O modelo escolhido em D-01 é *pull* por cron, com `SMB_SYNC_INTERVAL_MINUTES=5` em T010. No pior caso, o áudio fica até 5 minutos parado antes de a varredura começar. Os 30 segundos descrevem apenas a operação de cópia, não o intervalo entre fim da gravação e disponibilidade para o auditor.

Como está escrito, T024 (validação manual) vai reprovar o cenário 1 em qualquer execução que não caia por sorte no início de um ciclo. Direção sugerida: decidir explicitamente entre reescrever o critério como "até 5 min + 30s de cópia" ou reduzir o intervalo do cron; ambos exigem alterar `requirements.md`, o que sai de `/reversa-clarify` ou edição manual.

### A003 — RF-07 sem ação correspondente (HIGH)

RF-07 é classificado como Must e sustenta o principal requisito de segurança da feature (auditoria não pode apagar prova). Ele aparece como prosa no passo 1 do plano de migração do roadmap, mas nenhuma linha de `actions.md` o implementa ou verifica. Consequência prática: o critério de pronto pode ser declarado satisfeito com todas as ações `[X]` e o share ainda permitir escrita pela conta de auditoria.

Direção sugerida: acrescentar ação explícita — mesmo que seja de infraestrutura manual, com verificação registrada — antes de considerar o `actions.md` fechado.

### A004 — Cópia pode capturar `.mp3` em conversão (HIGH)

O `.mp3` é produzido por ffmpeg em processo assíncrono disparado por `upload_audio_chunk`. Entre o início e o fim da conversão o arquivo existe, tem tamanho crescente e mtime recente. T017 monta a fila por mtime e não checa se a escrita terminou, então uma varredura que caia nessa janela copia um arquivo parcial. O agravante é que T015 calcula o SHA256 da origem no momento da leitura: origem truncada e destino truncado batem, e a validação passa.

Direção sugerida: definir critério de estabilidade (por exemplo, ignorar arquivos com mtime nos últimos N segundos, ou comparar tamanho em duas leituras) e registrar isso como decisão no roadmap antes de codar T015/T017.

### A005 — Áudios que ficaram só em `.raw` nunca são copiados (HIGH)

`upload_audio_chunk` tem retorno `uploaded_raw_only` quando a conversão falha: o áudio bruto está salvo e nada é perdido localmente, mas não existe `.mp3`. T017 varre apenas `*.mp3`, então essas chamadas simplesmente não aparecem no share de auditoria — silenciosamente, sem entrada no log de transferência e sem métrica de falha. Para uma feature cujo propósito é auditoria, ausência silenciosa é pior do que erro visível.

Direção sugerida: decidir se `.raw` também é copiado, se é convertido em retentativa, ou se ao menos gera alerta; a decisão pertence ao roadmap.

### A006 — Justificativa de decisão baseada em precedente inexistente (HIGH)

D-07 escolhe `.env` em vez de gerenciador de segredos apoiado em "padrão já aplicado em projeto para S3", e `investigation.md` descreve o worker existente como "upload assíncrono a S3". Verificação: não há `boto3` nem qualquer cliente S3 em `src/`, `requirements.txt` não traz biblioteca S3, e `audio_uploader.py` grava em disco local e converte com ffmpeg. As regras R30 e R31 do `domain.md`, que também falam de S3, são resquício de uma versão anterior do código.

A decisão de usar `.env` continua defensável pelo argumento de rede privada (que o usuário confirmou explicitamente), mas a justificativa registrada precisa ser corrigida para não induzir a próxima pessoa a erro.

## Itens verificados que passaram

### Cobertura

- RF-02 (log de transferência) → D-02 → T012, com teste em T008
- RF-03 (retentar quando SMB cai) → D-06 → T016 e T017
- RF-04 (backoff exponencial e circuit breaker) → D-06 → T016
- RF-05 (checksum SHA256) → D-05 → T015 (ressalva em A004)
- RF-06 (throttling global) → D-04 → T014, com teste em T009
- RF-08 (poda do log após 7 dias) → D-02 → T012, com teste em T008
- Cenário Gherkin "arquivo deletado antes de copiar é pulado" → T017 e T008
- Cenário Gherkin "throttling protege a rede" → T014, T009 e T024

### Consistência

- Nomenclatura estável nos três documentos: `tenant`, `call_id`, `origem`, `destino`, `tx`/`rx`, `status=done|pending`
- Nenhum identificador fantasma: todos os `RF-xx`, `RN-xx` e `D-xx` citados existem nos documentos de origem
- O contrato descrito em `interfaces/smb.md` aparece no roadmap, seção 7
- O formato de nome de arquivo é idêntico em `requirements.md` RN-03, `roadmap.md` D-03, `data-delta.md`, `interfaces/smb.md` e `actions.md` T011

### Coerência com o legado

- `rx.mp3` e `tx.mp3` **realmente** são produzidos: `ingestor.py:51-56` de-intercala o frame estéreo em tx e rx, e `_handle_channel_hangup` (`esl_client.py:255-259`) acumula todos os chunks por canal antes de enfileirar um único upload — logo o modo `"wb"` de `upload_audio_chunk` não trunca a gravação. A premissa central de RF-01 se sustenta
- O padrão de worker cron `arq` invocado por T010 existe de fato em `audio_cleanup.py::WorkerSettings`
- `tenacity==9.0.0` já está em `requirements.txt`, então T016 não introduz dependência nova
- `Repository` e as Strategies de `src/services/base.py` existem, sustentando T013 e T020
- As colunas `caller_number` e `callee_number` existem em `Call` (`models.py:64-65`), então T018/T019 são alteração de preenchimento, não de schema — nenhuma migração Alembic é necessária, como `data-delta.md` afirma
- O volume `zenith_recordings_tmpfs` e o service `arq-uploader` citados por T021 existem em `docker-compose.app.yml`

### Sanidade do actions

- 26 ações, IDs sequenciais T001–T026, sem duplicata e sem reciclagem
- Todas as dependências apontam para IDs existentes dentro do próprio documento
- Nenhum ciclo de dependência: o grafo só referencia IDs anteriores
- Todos os status iniciam em `[ ]`
- Paralelismo correto na Fase 1 (T001–T006 em seis arquivos distintos) e na Fase 5 (T025 e T026 em arquivos distintos); exceção registrada em A008

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-27 | Versão inicial gerada por `/reversa-audit` | reversa |
