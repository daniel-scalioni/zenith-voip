---
adr:
  id: ADR-011
  status: accepted
  date: 2026-07-31
  components: [database-migrations, database-multitenancy]
---

# ADR-011: Baseline Alembic pública e provisionamento explícito por tenant

## Contexto

A cadeia Alembic `001 → 002 → 003` nunca foi aplicada no único ambiente conhecido. Esse banco não
possui `public.alembic_version`: `public.tenants` e `public.pbxs` foram criadas pelo SQLAlchemy, e
as tabelas de negócio foram provisionadas diretamente no schema do tenant. Em banco vazio, as
revisões existentes colidem porque migrations distintas tentam criar tabelas de chamada sem schema
explícito.

O inventário de 2026-07-31 não encontrou outro ambiente implantado nem histórico Alembic aplicado.
O PostgreSQL operacional publica a porta 5433, portanto consumidores externos inativos não podem
ser excluídos. Ele e seu volume precisam permanecer intactos.

## Decisão

1. Substituir a cadeia local inválida por uma única baseline Alembic que gerencia somente
   `public.tenants`, `public.pbxs` e suas constraints/índices.
2. Nunca criar `calls`, `transcripts`, `call_insights` ou `stt_metrics` em `public`.
3. Provisionar cada `tenant_<slug>` explicitamente a partir de `TenantBase`, fora da baseline
   pública.
4. Preservar o fluxo normal que gera UUIDs e adicionar um caminho explícito de restore capaz de
   receber os UUIDs originais.
5. Provar upgrade, repetição idempotente, provisionamento e restore primeiro em
   `zenith-postgres-test`, depois ensaiar em `zenith-postgres-rehearsal`; ambos são isolados e sem
   porta publicada.
6. Construir `zenith-postgres-candidate` separado dos bancos de teste/rehearsal. O candidato não
   referencia o volume operacional como `external`.
7. Manter `zenith-postgres` e `zenith-voip_zenith_postgres_data` disponíveis e inalterados até
   aceite humano posterior ao cutover.

## Guard de validade

Se qualquer ambiente com `alembic_version` aplicada for descoberto antes da implementação ou do
cutover, esta decisão de squash fica suspensa. Nesse caso, deve ser criada nova ADR e uma cadeia
compatível com a revisão encontrada; migrations aplicadas nunca serão reescritas.

## Consequências

### Positivas

- `alembic upgrade head` passa a ter uma única responsabilidade sobre estruturas globais.
- O isolamento schema-per-tenant deixa de depender de `search_path` implícito em migration.
- Testes, ensaio e candidato não compartilham dados, rede ou lifecycle com o operacional.
- O rollback é reapontar serviços ao PostgreSQL anterior, sem restauração destrutiva.

### Negativas

- Evoluções futuras de tabelas de tenant exigirão uma política explícita de rollout por schema;
  a baseline pública não as atualizará.
- O restore precisa de um caminho controlado para UUIDs explícitos.
- Durante o período de aceite existirão volumes adicionais que só poderão ser descartados após
  autorização e verificação dos manifests.

## Alternativas consideradas

| Alternativa | Decisão |
|-------------|---------|
| Corrigir apenas a revisão 003 | Rejeitada: 001 já mistura estruturas públicas e de tenant |
| Criar uma revisão 004 corretiva | Rejeitada: a cadeia falha antes de alcançar 004 |
| Marcar o banco atual com `stamp` | Rejeitada: declararia um estado que nunca foi produzido pela cadeia |
| Recriar o volume atual | Rejeitada: exclusividade externa não pode ser provada e o rollback seria degradado |
| Baseline pública + provisionador por tenant | Aceita |

## Critérios de aceite

- Duas execuções de `alembic upgrade head` em banco vazio terminam sem erro.
- `public` contém somente estruturas globais e `alembic_version`.
- Um tenant novo recebe somente suas tabelas de negócio.
- Restore preserva UUIDs, contagens e hashes do manifesto sanitizado.
- Nenhum recurso novo publica porta no host ou referencia o volume operacional.

## Relacionados

- `_reversa_sdd/adrs/001-multitenancy-schema-per-tenant.md`
- `_reversa_sdd/database/migrations/requirements.md`
- `_reversa_sdd/database/migrations/design.md`
- `_reversa_forward/011-smb-audio-backup/investigation.md`
