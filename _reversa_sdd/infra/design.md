# Infraestrutura, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Topologia Docker

```
[BunkerWeb :80/:443]
    ├── zenith-api-1  (:8000)
    └── zenith-api-2  (:8001)
           │
    ┌──────┴──────┐
    │   Redis 7   │
    │   Postgres  │
    │   Ollama    │  ← GPU reservada
    │   Piper     │
    └──────┬──────┘
           │
    zenith-worker (ARQ)
           │
    ┌──────┴──────┐
    │  Prometheus │
    │  Grafana    │
    │  Loki       │
    └─────────────┘

FreeSWITCH (network_mode: host, fora do Docker bridge)
```

### Serviços (14 containers)

| Serviço | Imagem | Portas (Host : Container) | Container Name |
|---------|--------|--------|----------------|
| bunkerweb | bunkerity/bunkerweb:1.5.12 | 80:80, 443:443 | zenith-bunkerweb |
| zenith-api-1 | Dockerfile (app) | 127.0.0.1:8001:8000 | zenith-api-1 |
| zenith-api-2 | Dockerfile (app) | 127.0.0.1:8002:8000 | zenith-api-2 |
| zenith-worker | Dockerfile (worker) | - | zenith-arq-uploader, zenith-arq-cleanup |
| postgres | postgres:16-alpine | 5433:5432 | zenith-postgres |
| redis | redis:7-alpine | - : 6379 | zenith-redis |
| ollama | ollama/ollama:0.5.7 | 11434:11434 | zenith-ollama |
| piper-tts | - | - | - |
| freeswitch | safarov/freeswitch:1.10.12 | SIP/ESL (host network) | zenith-freeswitch |
| prometheus | prom/prometheus:v2.55.1 | 9091:9090 | zenith-prometheus |
| grafana | grafana/grafana:11.3.0 | 3002:3000 | zenith-grafana |
| loki | grafana/loki:3.2.1 | 3102:3100 | zenith-loki |

## Sticky Session (BunkerWeb)

- Roteamento baseado em header `X-Call-ID`
- Garante que o mesmo WebSocket sempre caia na mesma instância FastAPI
- Configurado em `docker-compose.app.yml:136-138`

## Deploy

1. `deploy.sh` executa deploy com backup do compose atual — `deploy.sh:15-30`
2. Nova stack iniciada ao lado da atual
3. Health check valida antes de migrar tráfego
4. Rollback automático se health check falhar — `deploy.sh:40-50`

## Riscos e Lacunas

- 🔴 JWT_SECRET = "change-me-in-production" — senha default no config
- 🔴 ESL password = "ClueCon" — default do FreeSWITCH
- 🔴 S3 credentials expostas via env no compose
- 🟡 Sem secrets management (Vault, etc.)
- 🟡 FreeSWITCH em network_mode host — sem isolamento de rede
