# Database, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar engine assíncrona PostgreSQL + session factory
  - Origem: `src/database/database.py:10-20`
  - Critério: conexão estabelecida com pooling
  - Confiança: 🟢

- [ ] T-02, Implementar multitenancy com schema-per-tenant
  - Origem: `src/database/database.py:33-37`
  - Critério: cada tenant tem schema isolado; search_path ajustado por sessão
  - Confiança: 🟢

- [ ] T-03, Implementar modelos ORM (Tenant, PBX, Call, Transcript, CallInsight, STTMetric)
  - Origem: `src/database/models.py`
  - Critério: 6 modelos com relacionamentos, FKs, índices
  - Confiança: 🟢

- [ ] T-04, Implementar GenericRepository
  - Origem: `src/services/base.py:40-60`
  - Critério: CRUD genérico para qualquer modelo
  - Confiança: 🟢

- [ ] T-05, Configurar Alembic com migrations iniciais
  - Origem: `alembic/versions/001_initial.py`, `002_tenants_pbxs.py`, `003_tenant_schema_tables.py`
  - Critério: 3 revisões executáveis
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar criação de tenant com schema isolado
- [ ] TT-02, Testar CRUD via GenericRepository
- [ ] TT-03, Testar isolamento de dados entre tenants
