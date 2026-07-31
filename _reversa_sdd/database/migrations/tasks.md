---
spec:
  component: database-migrations
  layer: database
  status: active
  version: 2.0.0
  language: python
  patterns: [repository]
  inputs: []
  outputs: []
  dependencies:
    - {component: database-models, layer: database}
  events_produced: []
  updated_at: 2026-07-31
---

# Migrations, Tarefas de alto nível

- [x] Registrar ADR da baseline pública e do provisionamento por tenant.
- [x] Inventariar todos os ambientes antes de autorizar squash.
- [ ] Escrever testes Red para upgrade vazio, segunda execução, topologia e isolamento.
- [ ] Escrever teste Red de restore preservando UUIDs e dados.
- [ ] Implementar baseline pública mínima.
- [ ] Tornar o provisionador capaz de receber UUIDs explícitos no restore.
- [ ] Criar banco de teste dedicado e teardown seguro.
- [ ] Ensaiar dump/restore em volume PostgreSQL novo com prefixo `zenith-`.
- [ ] Executar cobertura global ≥ 80% e testes E2E.
- [ ] Executar corte reversível preservando o volume anterior.
