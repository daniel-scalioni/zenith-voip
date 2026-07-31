---
spec:
  component: database-migrations
  layer: database
  status: active
  version: 2.0.0
  language: python
  patterns: [repository]
  inputs:
    - {name: database_url, type: PostgreSQL DSN, from: environment}
  outputs:
    - {name: public_schema, type: PostgreSQL schema, to: database}
    - {name: tenant_schema, type: PostgreSQL schema, to: database}
  dependencies:
    - {component: database-models, layer: database}
  events_produced: []
  updated_at: 2026-07-31
---

# Migrations (database/migrations)

## Estado comprovado

A cadeia `001 → 002 → 003` nunca foi aplicada com sucesso no ambiente conhecido. O banco de
produção não possui `public.alembic_version`; `public.tenants` e `public.pbxs` foram criadas por
SQLAlchemy, e o schema `tenant_akom` foi criado por `create_tenant_schema()`. Em banco vazio, 001 e
003 tentam criar as mesmas tabelas sem schema explícito e colidem.

## Requisitos da recuperação

| ID | Requisito | Critério |
|----|-----------|----------|
| MIG-RF-01 | Uma baseline Alembic deve criar somente as estruturas públicas globais | Banco vazio recebe `public.tenants`, `public.pbxs` e `public.alembic_version` sem tabelas de chamada em `public` |
| MIG-RF-02 | Schemas de tenant devem ser provisionados de forma explícita e isolada | `tenant_<slug>` recebe `calls`, `transcripts`, `call_insights` e `stt_metrics`; não recebe `tenants` ou `pbxs` |
| MIG-RF-03 | `alembic upgrade head` deve funcionar do zero e ser no-op quando repetido | Duas execuções consecutivas terminam sem erro e mantêm a mesma revisão |
| MIG-RF-04 | Testes de banco jamais podem usar o banco operacional | DSN de teste aponta para recurso `zenith-*` dedicado e o teardown remove somente os objetos daquele teste |
| MIG-RF-05 | Recriação deve preservar tenant, PBX e chamadas existentes | UUIDs e contagens antes/depois são idênticos; hoje: 1 tenant, 1 PBX e 9 chamadas no tenant operacional |
| MIG-RF-06 | O volume PostgreSQL atual permanece intacto até o novo ambiente passar todos os gates | Rollback consiste em voltar os serviços ao volume anterior, sem restauração destrutiva |
| MIG-RF-07 | Configuração de ramais FreeSWITCH deve ser regenerável e verificada após o corte | CSV privado gera 939 usuários/gateways e preserva o conjunto ativo, sem expor credenciais |
| MIG-RF-08 | Squash só é permitido após inventário de todos os ambientes conhecidos | Se qualquer ambiente possuir histórico Alembic aplicado, abandonar o squash e criar caminho compatível |
