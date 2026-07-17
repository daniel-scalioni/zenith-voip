# Módulo: infra

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito |
|---------|-----------|
| `Dockerfile` | Build da aplicação (Python 3.12-slim) |
| `docker-compose.yml` | Orquestrador (include app + infra) |
| `docker-compose.app.yml` | Serviços da aplicação (9 containers) |
| `docker-compose.infra.yml` | Serviços de infraestrutura (5 containers) |
| `prometheus.yml` | Config do Prometheus |
| `grafana/dashboards/ai-hub.json` | Dashboard Grafana |
| `freeswitch/conf/` | Configurações FreeSWITCH |
| `bootstrap.sh` | Setup do ambiente de dev |
| `deploy.sh` | Deploy automatizado |
| `scripts/bump-version.sh` | Bump de versão |

## Topologia Docker

### Infraestrutura (docker-compose.infra.yml)
- PostgreSQL 16-alpine (porta do host 5433, container 5432)
- Redis 7-alpine com appendonly (comunicação interna via rede Docker bridge, sem porta exposta no host)
- Prometheus v2.55.1 (porta do host 9091, container 9090)
- Grafana 11.3.0 (porta do host 3002, container 3000)
- Loki 3.2.1 (porta do host 3102, container 3100)

### Aplicação (docker-compose.app.yml)
- FreeSWITCH 1.10.12 (network_mode: host, container_name: zenith-freeswitch)
- FastAPI-1 (porta 8001 no host)
- FastAPI-2 (porta 8002 no host)
- ARQ Cleanup Worker
- BunkerWeb (portas 80/443, container_name: zenith-bunkerweb) — reverse proxy com sticky session
- Ollama 0.5.7 (porta 11434, GPU opcional)
- Piper TTS (removido, integrado localmente via API Python)

### Infra de Rede
- Subnet: 172.20.0.0/16
- Bridge: ai-hub-net

## Estratégia de Deploy

- `deploy.sh` suporta: staging/production com tags Git
- Registro de revisões em `revisions.json`
- Health check pós-deploy (até 12 tentativas)
- Rollback para versão anterior
- CI/CD: nenhum (deploy manual via script)

## Config FreeSWITCH

- SIP profile internal: portas 5060/5061, TLS opcional, codecs negociáveis
- Dialplan default
- Módulos: autoload_configs

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Duas instâncias FastAPI para HA | `docker-compose.app.yml:28-92` | 🟢 |
| Sticky session via X-Call-ID (BunkerWeb) | `docker-compose.app.yml:136-138` | 🟢 |
| GPU reservada para Ollama | `docker-compose.app.yml:158-164` | 🟢 |
| FreeSWITCH em network_mode host | `docker-compose.app.yml:16` | 🟢 |
