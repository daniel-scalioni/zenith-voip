# ADR-001: Multitenancy com Schema por Tenant

> **Data:** 2026-05-17 (inferido da criação da migration 001 → 002 → 003)
> **Status:** Aceito 🟢
> **Confiança:** 🟡 INFERIDO (baseado na evolução das migrations)

## Contexto

O sistema precisava suportar múltiplos clientes (tenants) com isolamento total de dados. A abordagem inicial (migration 001) colocava `tenant_id` como coluna na tabela `calls`, mas foi substituída por schemas PostgreSQL isolados.

## Decisão

Usar **schema-per-tenant**: cada tenant recebe um schema PostgreSQL dedicado (`tenant_{id}`) com suas próprias tabelas de dados transacionais (calls, transcripts, call_insights, stt_metrics). Metadados dos tenants (Tenant, PBX) ficam no schema `public`.

## Alternativas Consideradas

| Alternativa | Motivo da Rejeição |
|-------------|-------------------|
| Coluna tenant_id em todas as tabelas | Abordagem inicial (v001) — risco de vazamento de dados entre tenants, complexidade em queries multi-tenant |
| Banco separado por tenant | Custo operacional elevado, complexidade de conexão |
| Row-Level Security (RLS) | Recurso avançado do PostgreSQL, maior acoplamento |

## Consequências

- **Positivas:** Isolamento total de dados, backup/restore por tenant, sem risco de contaminação cross-tenant
- **Negativas:** Migrations precisam rodar por schema, complexidade em queries que cruzam tenants, necessidade de criar schema dinamicamente
- **Neutras:** Pool de conexões compartilhado com `search_path` por sessão
