---
spec:
  component: deployment
  layer: infra
  status: active
  version: 1.1.0
  language: yaml
  patterns: []
  inputs: [{name: compose_environment, type: environment, from: operator}]
  outputs: [{name: zenith_stack, type: containers, to: runtime}]
  dependencies: []
  events_produced: []
  updated_at: 2026-08-18
---

# Deploy (infra/deployment)

**Responsabilidades:** Orquestração Docker, BunkerWeb, deploy automatizado com rollback
**Regras:** 2 instâncias FastAPI; sticky session X-Call-ID; GPU Ollama; FS host 🟢
**Origem:** `docker-compose*.yml`, `Dockerfile`, `deploy.sh`

## PostgreSQL promovido

- O serviço canônico continua se chamando `postgres` na rede da aplicação para preservar o DNS
  consumido por todos os serviços. 🟢
- O container promovido é `zenith-postgres-candidate` e usa o volume persistente existente
  `zenith-postgres-candidate-data`; o Compose não pode reintroduzir `zenith-postgres` nesse alias. 🟢
- Usuário, banco e senha do PostgreSQL promovido devem coincidir com `DATABASE_URL`; a senha do
  container é obrigatória via `ZENITH_CANDIDATE_POSTGRES_PASSWORD`, e a URL completa, com senha
  URL-encoded, é obrigatória via `DATABASE_URL`. Nenhuma recebe default versionado. 🟢
