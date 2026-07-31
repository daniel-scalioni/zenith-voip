# Cross-check: SMB Audio Backup para Auditoria

> Data: `2026-07-28`
> Feature: `011-smb-audio-backup`
> Artefatos: [`requirements.md`](../requirements.md) · [`roadmap.md`](../roadmap.md) · [`actions.md`](../actions.md)

## Resumo

| Severidade | Quantidade |
|------------|-----------:|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |

## Findings

Nenhum finding aberto.

## Findings anteriores resolvidos

| Finding anterior | Evidência de resolução |
|------------------|------------------------|
| SLA de 30 s versus timeout de 60 s | Requirements, D-19, interface, T051 e T017 fixam orçamento global bloqueante de 30 s para geração estéreo + cópia |
| Lease sem duração ou renovação | RF-11, D-14, T045 e T046 fixam UTC, validade de 120 s, renovação a cada 30 s e tratamento de conteúdo inválido/corrompido |
| Caminho divergente do log | Contrato canônico unificado em `/data/smb_logs/smb_transfer_log.json` |
| Estados divergentes do log | Requirements, roadmap e actions usam `pending`, `done` e `failed` |
| Tarefas paralelas compartilhando alvo | Marcadores removidos de T005, T020 e T041; nenhuma tarefa `[//]` compartilha arquivo alvo |

## Verificações aprovadas

### Cobertura

- RF-01 a RF-12 possuem decisões correspondentes no roadmap.
- D-01 a D-19 possuem ações de preparação, testes, implementação ou validação.
- Todos os cenários Gherkin possuem cobertura por decisão e ação.
- O timeout global possui teste Red dedicado em T051 antes da implementação em T017.
- Lock, lease, cleanup, recuperação de JSON, colisão e remoção do estéreo possuem pares
  teste/implementação.
- O mini-spike `pysmb==1.2.14` precede a validação E2E.

### Consistência

- SLA e timeout usam 30 s em requirements, roadmap, interface, onboarding e actions.
- Lease usa UTC, validade de 120 s e renovação de 30 s em todos os artefatos.
- Caminho e estados do log são uniformes.
- Mapeamento left=`tx` e right=`rx`, nome remoto, sufixo de colisão, checksum, assinatura,
  Direct TCP/445 e NTLMv2 são coerentes.
- Conta técnica WRITE e conta de auditoria READ-ONLY permanecem separadas.
- Não existem identificadores RF ou D fantasmas.

### Coerência com o legado

- O estéreo é derivado; `tx.mp3` e `rx.mp3` permanecem separados, preservando R39–R41.
- Falha de conversão preserva `.raw`, coerente com R40.
- O worker ARQ mantém SMB fora da cadeia crítica de gravação.
- A retenção de aproximadamente 1 h para 2 h está registrada como delta explícito.
- Os campos de chamada utilizados já existem; não há migração PostgreSQL.
- Recursos Docker novos mantêm o prefixo `zenith-`/`zenith_`.

### Sanidade do actions

- 51 IDs únicos.
- Todas as dependências apontam para IDs existentes.
- Não há ciclo de dependência.
- 13 tarefas `[//]`; nenhuma compartilha arquivo alvo com outra ação.
- Maior cadeia de dependência recalculada: 18.
- T001 precede alterações de dependência, ambiente e Compose, preservando spec-first.
- TDD está explícito: testes Red antecedem as respectivas implementações.

## Veredito

Os artefatos estão coerentes e aptos a seguir para `/reversa-coding`. Nenhum dos artefatos
auditados foi alterado por esta auditoria.

---

## Cross-check da decomposição de recuperação dos gates — 2026-07-30

O quadro anterior permanece como histórico da entrega SMB. A decomposição foi ampliada para
T001–T115 devido aos gates globais de Alembic, banco de teste e cobertura.

### Modelos e lentes

| Modelo/CLI | Lente | Achados incorporados |
|------------|-------|----------------------|
| Claude Sonnet / Claude CLI | atomicidade e DAG | inventário antes do ADR; três bancos distintos; rollback antes do cutover; spec `active`; coleta `tests/` + `src/`; checkpoint humano |
| DeepSeek V4 Flash / OpenCode | TDD anti-viés | separar Red/Green; revisão por grupo de diffs; banco isolado; caminhos infelizes; tarefas de cobertura por domínio |
| Mimo V2.5 / OpenCode | segurança operacional | não tocar PostgreSQL atual; recursos sem porta publicada; candidato/rehearsal com volumes próprios; health entre recreações |

### Divergências julgadas

- A sugestão de escolher portas 5434/5435 foi substituída por opção mais restritiva: nenhum banco
  novo publica porta no host; administração ocorre dentro da rede/runner Zenith.
- A porta 5433 atual não será fechada nesta feature, pois isso modificaria um recurso cuja
  exclusividade externa não pode ser provada.
- O E2E SMB não foi duplicado nas novas tarefas; T024 continua sua única fonte de verdade.

### Sanidade final

- 115 IDs únicos e contínuos.
- 35 tarefas `[//]`.
- Todas as dependências apontam para IDs existentes.
- Nenhum ciclo no grafo.
- Maior cadeia de dependência: 30.
- T104 é checkpoint humano bloqueante; T105 não inicia automaticamente.
- `zenith-postgres` e seu volume não são alvo de stop, recreate, reconfiguração ou remoção.

## Veredito atualizado

A decomposição está apta para `/reversa-coding`, iniciando somente pela Preparação T056–T065.
