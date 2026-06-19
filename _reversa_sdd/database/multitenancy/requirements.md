# Multitenancy (database/multitenancy)

**Responsabilidades:** Schema PostgreSQL isolado por tenant, scoped sessions
**Regras:** Schema `tenant_{id}`; public para tabelas globais 🟢
**Origem:** `src/database/database.py`
