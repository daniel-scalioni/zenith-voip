# Cross-check: Captura de áudio em WAV 16 kHz na origem

> Data da auditoria: `2026-08-13`
> Feature: `014-captura-wav-16k`
> Artefatos auditados: [requirements.md](../requirements.md) · [roadmap.md](../roadmap.md) · [actions.md](../actions.md)
> Escopo: cobertura, consistência, coerência com o legado, contratos e sanidade das ações

## Resumo

| Severidade | Findings |
|------------|----------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 4 |
| LOW | 0 |
| **Total** | **6** |

## Findings

| ID | Severidade | Eixo | Descrição | Onde está |
|----|------------|------|-----------|-----------|
| A001 | HIGH | Cobertura / consistência | O contrato do arquivo durante a chamada é contraditório. RN-05 diz `.raw` ou `.tmp.wav`, RF-09 e seu Gherkin exigem que `.raw` exista e cresça antes do hangup; D-03/D-14, a interface e T001/T008/T020/T038 exigem exclusivamente `<channel>.tmp.raw`, mantendo `.raw` invisível até a finalização. A implementação planejada não consegue satisfazer literalmente o aceite atual de RF-09. | `requirements.md:76-78,127,167-171`; `roadmap.md:37-42,87,98`; `actions.md:T001,T008,T020,T038`; `interfaces/recording-audio-files.md:20,48` |
| A002 | HIGH | Cobertura | RF-05 é Must e o cenário de capacidade exige que o pior caso previsto de chamadas simultâneas permaneça abaixo de 100% do tmpfs. O roadmap mantém 512 MB, calcula ~460 MB para uma única chamada de 1 h e declara que não há correção no escopo; T040 apenas mede e registra uma decisão se a capacidade for insuficiente. Falta uma decisão/ação condicionada que garanta o critério de aceite antes de considerar a feature pronta. | `requirements.md:123,135,185-189,203`; `roadmap.md:60-62,74,166,187-188`; `actions.md:T040` |
| A003 | MEDIUM | Consistência | O limiar de vazão de RF-01 está duplicado por um fator de dois: informa ~64 kB/s por canal em 16 kHz e ~32 kB/s por canal em 8 kHz. Para PCM16 mono, o contrato de 16000 Hz implica 32000 bytes/s por canal (e 16000 bytes/s a 8 kHz), valores também usados pelo onboarding. O aceite atual rejeitaria uma captura correta. | `requirements.md:119`; `interfaces/recording-audio-files.md:16-18`; `onboarding.md:54-55` |
| A004 | MEDIUM | Consistência terminológica | O resumo executivo descreve a alteração do comando como `stereo 8k` → `16k`, embora RN-01, D-01 e as ações determinem o token numérico `16000` e registrem que o módulo não reconhece o sufixo. O Gherkin também usa “capturando ... em 16k”, deixando ambíguo se é taxa humana ou argumento literal. | `requirements.md:11-14,54-60,143-145`; `roadmap.md:D-01`; `actions.md:T011,T022` |
| A005 | MEDIUM | Consistência de identificador | A interface afirma que RF-03 torna explícita a independência da extensão do `.md` da feature 013, mas RF-03 trata da adaptação do backup SMB e dos caminhos WAV. A independência do `.md` aparece em RN-08, não em RF-03; o identificador existe, porém aponta para o conteúdo errado. | `interfaces/recording-audio-files.md:42-46`; `requirements.md:95-102,121` |
| A006 | MEDIUM | Sanidade / TDD | T031 implementa instrumentação de ocupação e confirmações pendentes, mas nenhuma ação Red anterior exige o comportamento dessa métrica/log. T018 cobre a política de cleanup, não explicita observabilidade. Isso quebra a ordem TDD declarada pelo roadmap e pela regra bloqueante do projeto para uma mudança de código. | `roadmap.md:76-77`; `actions.md:T018,T031,T032`; `AGENTS.md`, seção TDD |

## Impacto e direção de correção

### A001 — contrato transitório incompatível

O teste de aceite pode exigir `.raw` durante a chamada exatamente quando D-14 proíbe sua existência
para impedir publicação truncada e cleanup prematuro. Antes do coding, alinhe RN-05, RF-09 e o
Gherkin com o contrato já consolidado de `.tmp.raw` → `.raw` → `.wav`. Use `/reversa-clarify` para
revisar o requisito ou faça edição manual dos artefatos; este skill não executa a correção.

### A002 — capacidade sem condição de aprovação

Uma medição que exceda o teto ainda deixaria todas as ações executadas, mas o requisito Must e o
Gherkin continuariam reprovados. Antes do coding/deploy, defina no requirements/roadmap uma condição
objetiva de aprovação e uma ação de mitigação autorizável, por exemplo ajustar o tmpfs se o pico
medido ultrapassar uma margem segura. Use `/reversa-clarify` para obter a decisão humana e depois
regenere plano/ações, ou faça revisão manual; este skill não altera infraestrutura nem artefatos.

## Verificações aprovadas

### Cobertura

- RF-01 a RF-08 possuem decisões e ações correspondentes; RF-09 possui rastreabilidade, com a
  incompatibilidade de nome transitório isolada em A001.
- D-01 a D-15 aparecem em pelo menos uma ação executável.
- Os cenários de WAV final, backup SMB, consumo confirmado, fallback por TTL, MP3 legado e falha de
  conversão possuem testes e/ou validações operacionais correspondentes.
- RF-06 está coberto pelos gates T032, T033 e T035; o veredito anti-viés está em T036.

### Consistência e contratos

- RF-01 a RF-09 existem; não há RF fantasma nos três artefatos principais.
- O D-20 citado no plano de migração está explicitamente qualificado como decisão histórica da
  feature 011, não como decisão desta feature.
- O contrato `interfaces/recording-audio-files.md` aparece no delta de contratos do roadmap e suas
  propriedades centrais — WAV PCM16, 16 kHz, canais separados e estéreo SMB — estão cobertas pelas
  ações.
- Os termos `tx`, `rx`, `stereo.wav`, `.consumed-<consumer>` e
  `RECORDING_REQUIRED_CONSUMERS` são usados consistentemente, ressalvados os findings acima.

### Coerência com o legado e arquitetura

- As alterações conscientes das regras verdes R39/R41 (MP3 8 kHz e extensão `.mp3`) estão
  declaradas como delta, não escondidas como preservação de comportamento.
- R40 (preservar `.raw` em falha), R42 (captura via ESL) e R43 (pares `tx`, ímpares `rx`) são
  preservadas no roadmap e nas ações.
- R38 permanece respeitada: o armazenamento continua no `zenith_recordings_tmpfs` de 512 MB; o
  risco de capacidade está explicitado em A002.
- FreeSWITCH, ESLClient, AudioIngestor, Workers ARQ e tmpfs existem em `architecture.md`;
  `recording-consumers` está identificado como componente novo, não como componente legado
  inexistente.

### Sanidade de `actions.md`

- 40 IDs únicos e sequenciais (`T001` a `T040`).
- Todas as dependências apontam para IDs existentes.
- O grafo de dependências é acíclico.
- As 19 ações `[//]` não compartilham arquivo alvo entre si.
- O resumo de total, paralelismo e maior cadeia de dependência confere com as tabelas.
- As ações de preparação precedem testes Red, e os testes precedem o núcleo, salvo a lacuna
  específica de observabilidade em A006.

## Integridade da auditoria

Esta auditoria não alterou `requirements.md`, `roadmap.md`, `actions.md`, `data-delta.md`,
`interfaces/`, `investigation.md` nem `onboarding.md`. O único artefato escrito foi este relatório.
