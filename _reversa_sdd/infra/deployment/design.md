# Deploy, Design

**Stack:** 14 containers Docker, BunkerWeb proxy, FreeSWITCH host network
**HA:** 2 instâncias FastAPI com sticky session via X-Call-ID
**GPU:** Reservada para Ollama via docker-compose device mapping
**Deploy:** deploy.sh com backup + health check + rollback
**Origem:** `docker-compose.app.yml:136-164`, `deploy.sh` 🟢
