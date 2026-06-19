# Database — Banco de Dados

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Camada de persistência PostgreSQL com multitenancy físico (schema-per-tenant), ORM SQLAlchemy, migrations Alembic e scoped sessions por tenant.

## Responsabilidades

- Gerenciamento de conexão PostgreSQL via SQLAlchemy async
- Multitenancy físico: schema PostgreSQL isolado por tenant
- CRUD base via GenericRepository (Strategy Pattern)
- Migrations via Alembic (3 revisões)

## Regras de Negócio

- Cada tenant tem schema PostgreSQL isolado (`tenant_{id}`) 🟢
- Tabelas globais (tenants, pbxs) no schema `public` 🟢
- PBX pertence a um tenant com FK CASCADE 🟢
- Chamadas e transcrições residem no schema do tenant 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Conectar ao PostgreSQL via asyncpg | Must |
| RF-02 | Gerenciar schemas de tenants (criação/isolamento) | Must |
| RF-03 | Prover sessão scoped por tenant | Must |
| RF-04 | Prover repositório CRUD genérico | Must |
| RF-05 | Executar migrations via Alembic | Must |

## Rastreabilidade

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `src/database/database.py` | engine, session factory, tenant schema | 🟢 |
| `src/database/models.py` | Tenant, PBX, Call, Transcript, etc. | 🟢 |
| `alembic/versions/*` | Migrations | 🟢 |
