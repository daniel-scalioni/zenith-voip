# Auditoria cruzada — 013-transcricao-persistida

> Data: 2026-08-17
> Feature: `013-transcricao-persistida`
> Artefatos auditados: [requirements.md](../requirements.md), [roadmap.md](../roadmap.md) e [actions.md](../actions.md)
> Artefatos auxiliares consultados: `interfaces/transcript-md.md`, `data-delta.md`, `investigation.md`, `onboarding.md`, `_reversa_sdd/domain.md`, `_reversa_sdd/architecture.md` e os contratos/estado físico da feature `014-captura-wav-16k`

## Resumo

| Severidade | Quantidade |
|------------|------------|
| CRITICAL | 1 |
| HIGH | 5 |
| MEDIUM | 3 |
| LOW | 1 |

Veredito: **a feature 013 ainda não está pronta para `/reversa-coding`**. As ações pertencem corretamente à feature 013, mas o contrato e parte do plano ficaram defasados depois que a feature 014 passou a produzir WAV 16 kHz e introduziu um novo ciclo de leases/consumidores.

## Findings

| ID | Severidade | Eixo | Descrição | Onde está |
|----|------------|------|-----------|-----------|
| A001 | CRITICAL | Consistência / contrato de arquivo | A 013 exige e descobre `tx.mp3`/`rx.mp3` e usa `stereo.mp3` como referência, mas a 014 e o código atual produzem `tx.wav`/`rx.wav` e `stereo.wav` em PCM16 16 kHz. O próprio `actions.md` da 013 registra que T009/T021/T022 precisam ser revisadas. O consumidor planejado não encontra o contrato atual do produtor. | `requirements.md` RN-02/RN-03/RN-05 e RF-01/RF-03/RF-04; `roadmap.md` D-01/D-04/D-09; `actions.md` T009/T016/T021/T022 e nota de execução; `014-captura-wav-16k/interfaces/recording-audio-files.md` |
| A002 | HIGH | Coerência entre features | A retomada da 013 ocorreu antes do fechamento operacional da 014. A 014 ainda possui 6 ações abertas — rollout, chamadas/SMB/capacidade reais e checklist final — e seu RF-14/D-24 proíbe retomar a 013 antes dessas provas e do sync. | `.reversa/active-requirements.json`; `014-captura-wav-16k/actions.md` T037-T040/T060; `014-captura-wav-16k/requirements.md` RF-14; `014-captura-wav-16k/roadmap.md` D-24 e critério de pronto |
| A003 | HIGH | Cobertura roadmap → actions | A nota de execução identifica três correções necessárias em `WhisperCppSTT` — descoberta via `$PATH`, leitura correta da saída `-oj` e normalização de `confidence` — mas T008/T019 cobrem somente `shutil.which`. Assim, RF-01 pode não produzir texto e RF-03 pode publicar confidence negativa/incompatível com o contrato. | `actions.md` T008/T019 e nota de execução itens 3/retomada; `requirements.md` RF-01/RF-03; `interfaces/transcript-md.md#Formato do conteúdo`; `src/services/stt_whisper.py` |
| A004 | HIGH | Cobertura / ciclo de vida | O desenho da 014 substituiu a premissa simples de D-10 por leases por estágio e confirmação de consumidores. A 013 não possui ação explícita para registrar `transcript` em `RECORDING_REQUIRED_CONSUMERS`, adquirir/renovar o lease de estágio e chamar `mark_consumed` após concluir. T012/T024 miram apenas `transcript_batch.py`; sem a integração, o cleanup pode remover o WAV durante o STT ou manter a política de consumo incompleta. | `roadmap.md` D-10; `actions.md` T012/T024/T030 e nota de execução item 2; `014-captura-wav-16k/roadmap.md` D-09/D-10/D-12/D-17; `src/config.py`; `src/workers/recording_consumers.py` |
| A005 | HIGH | Cobertura roadmap → actions | Três decisões que o roadmap exigia antes das tarefas correspondentes não viraram ações inequívocas: timeout/retry do job, comportamento quando um canal está ausente/vazio e alinhamento temporal entre tx/rx. T009 cobre arquivo menor; T015 cobre ordenação, mas não resolve ausência de canal nem a origem/alinhamento dos timestamps. | `roadmap.md#10 Pontos ainda abertos`; `actions.md` T009/T015/T017/T021/T025 |
| A006 | HIGH | Sanidade / gates | A dependência dos gates está invertida: T036 valida chamada real em produção antes de T037 executar a suíte completa/cobertura e antes de T038 obter o veredito independente. O onboarding, o AGENTS.md e a própria 014 exigem gates antes do rollout/validação remota. | `actions.md` T036→T037→T038; `onboarding.md#2`; `AGENTS.md#Quality Gates`; `014-captura-wav-16k/requirements.md` RF-14 |
| A007 | MEDIUM | Consistência documental | D-06 e as ações adotam imagem/container dedicados (`Dockerfile.transcript`, `arq-transcript`), mas o delta arquitetural fala em alterar o `Dockerfile` da aplicação, o onboarding testa o binário em `zenith-api-1` e a investigação diz que o container dedicado foi adiado. | `roadmap.md` D-06 e delta arquitetural; `actions.md` T002/T003/T007/T031; `investigation.md#Alternativas`; `onboarding.md#1` |
| A008 | MEDIUM | Consistência / idempotência | D-03 exige dois sinais para pular uma chamada — linhas `Transcript` **e** `.md` remoto — enquanto `data-delta.md` ainda afirma que a existência de `Transcript` sozinha decide “já processado”. A nota posterior também troca a checagem remota por listagem de nomes, divergindo da descrição de checksum do roadmap. | `roadmap.md` D-03; `actions.md` T011/T023 e nota de execução item 5; `data-delta.md#Idempotência` |
| A009 | MEDIUM | Sanidade de dependências | T035 pode marcar F1 como implementada sem depender de nenhuma tarefa de implementação ou validação. Como está `[//]` e sem dependência, pode produzir documentação falsa antes do aceite. | `actions.md` T035 |
| A010 | LOW | Formato / orquestração | Os status das 38 ações estão em code span (`` `[ ]` ``). O detector físico documentado pelo `/reversa-forward` procura linhas terminadas em `| [ ] |`/`| [X] |`; esse formato impede a contagem literal e pode classificar incorretamente o estágio. | `actions.md`, coluna Status |

## Impacto e direção de correção — CRITICAL/HIGH

### A001 — contrato MP3/WAV incompatível

O worker descrito pela 013 procuraria arquivos que o pipeline atual não produz. Antes de codificar, o contrato de entrada, a referência do áudio remoto, os cenários e as tarefas precisam convergir para WAV PCM16 16 kHz. Use `/reversa-clarify` para integrar formalmente a decisão da 014 em `requirements.md`; depois regenere/revise roadmap e ações pelos skills correspondentes ou faça edição manual controlada.

### A002 — pré-requisito 014 ainda aberto

Sem rollout e validação real da 014, a 013 dependeria de um formato que passou nos testes locais, mas ainda não teve o contrato operacional fechado. Retome a 014 com `/reversa-resume`, conclua T037-T040/T060 e execute `/reversa-sync` antes de tornar a 013 ativa novamente.

### A003 — contrato real do Whisper não coberto

Corrigir apenas a descoberta do binário não prova que o JSON é lido do local correto nem que a confidence atende ao formato público. Use `/reversa-clarify` ou revisão manual para ampliar RF/D-05 e, depois, faça T008/T019 cobrirem os três comportamentos antes da implementação.

### A004 — integração com lifecycle da 014 ausente

O worker precisa participar do protocolo que evita remoção prematura e informa consumo concluído. Use `/reversa-clarify` para definir quando `transcript` é registrado e marcado como consumido, incluindo o caminho de falha/retry; depois acrescente testes e ações para configuração, lease e marcador.

### A005 — decisões operacionais sem tarefa

Timeout/retry, canal ausente e alinhamento temporal afetam caminhos infelizes e o formato final. Resolva-os em `/reversa-clarify` e transforme cada decisão em testes Red e ações explícitas antes do coding.

### A006 — gates depois da produção

A ordem atual permite validação remota antes da suíte bloqueante e do parecer independente. Revise manualmente as dependências para que suíte/cobertura, Alembic e advisor antecedam qualquer rollout ou chamada de produção.

## Itens verificados que passaram

### Cobertura

- RF-01 a RF-05 possuem decisões e ações correspondentes no desenho original baseado em MP3.
- Os três cenários Gherkin possuem cobertura planejada: geração/publicação do `.md`, isolamento da falha do Whisper e reprocessamento idempotente.
- O contrato `interfaces/transcript-md.md` está referenciado no roadmap e coberto por T015-T017/T027-T029.

### Consistência

- O identificador `013-transcricao-persistida` coincide em `active-requirements.json`, requirements, roadmap e actions; portanto, as ações auditadas pertencem à feature 013.
- RN-01 e o vocabulário `tx`→atendente / `rx`→cliente permanecem consistentes nos três artefatos.
- D-01 a D-11 existem e são referenciadas por ações; não há identificadores de tarefa fantasmas.

### Coerência com o legado

- O mapeamento de canais respeita a regra confirmada R43.
- O uso de Whisper.cpp local respeita a política de dados sensíveis locais/ADR-003.
- `Transcript`, `WhisperCppSTT`, workers ARQ, PostgreSQL schema-per-tenant e SMB existem na arquitetura e no código consultado.
- D-11 está coerente com o isolamento schema-per-tenant documentado.

### Sanidade das ações

- Foram encontrados 38 IDs únicos, T001-T038.
- Todas as dependências apontam para IDs existentes.
- O grafo de dependências é acíclico.
- As tarefas marcadas `[//]` não compartilham arquivo alvo entre si.

## Próximo passo sugerido

Há finding CRITICAL e findings HIGH. Faça revisão humana antes de `/reversa-coding`. A sequência segura é concluir e sincronizar a 014, retomar a 013 e usar `/reversa-clarify` para incorporar o contrato WAV e as decisões pendentes; depois regenere/revise roadmap e actions e rode `/reversa-audit` novamente.
