# Deploy, Design

**Stack:** 15 containers Docker (incluindo `arq-uploader`, novo), BunkerWeb proxy, FreeSWITCH host network
**HA:** 2 instâncias FastAPI com sticky session via X-Call-ID
**GPU:** Reservada para Ollama via docker-compose device mapping
**Deploy:** deploy.sh com backup + health check + rollback; `scripts/setup-recording-mvp.sh` para provisionar a infra do MVP de gravação (build do FreeSWITCH custom, migrations, workers)
**Storage de gravação:** disco local (`./data/recordings` no host, bind mount em `fastapi-1`/`fastapi-2`/`arq-uploader`/`arq-cleanup`) — decisão de produto em 2026-06-22, substitui S3 (nunca chegou a ser provisionado: `S3_ENDPOINT` vazio nos `.env.*.example`, sem MinIO no compose)
**Origem:** `docker-compose.app.yml`, `deploy.sh`, `scripts/setup-recording-mvp.sh` 🟢

## Risco em resolução (2026-06-22)

🟡 A imagem `safarov/freeswitch:1.10.12` referenciada no compose é uma build vanilla do FreeSWITCH — **não inclui `mod_audio_fork`** (confirmado via inspeção direta da imagem, módulo ausente). `freeswitch/Dockerfile` foi criado para compilar o módulo (fonte: `drachtio-freeswitch-modules`, contra `freeswitch-dev` do repositório APT da SignalWire) e empacotá-lo sobre a imagem original — requer um token de conta SignalWire (`freeswitch/signalwire_token.txt`, ver `freeswitch/signalwire_token.txt.example`), passado como build secret. **Ainda não validado contra build real** (sem Docker neste ambiente de análise) — ver GAP-11.
