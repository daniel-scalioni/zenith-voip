# Módulo: infra

> Gerado pelo Archaeologist — 2026-06-19
> **Re-extração incremental — 2026-07-27** (base `48da5b1` → `0658157`, deltas D-08/D-12/D-13/D-14)
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito |
|---------|-----------|
| `Dockerfile` | Build da aplicação (Python 3.12-slim) |
| `docker-compose.yml` | Orquestrador (include app + infra) |
| `docker-compose.app.yml` | Serviços da aplicação |
| `docker-compose.infra.yml` | Serviços de infraestrutura (5 containers) |
| `freeswitch/Dockerfile` 🆕 | Build próprio do FreeSWITCH com `mod_audio_stream` |
| `sidecar/Dockerfile` 🆕 | Build do watcher de IP externo |
| `prometheus.yml` | Config do Prometheus |
| `grafana/dashboards/ai-hub.json` | Dashboard Grafana |
| `freeswitch/conf/` | Configurações FreeSWITCH |
| `bootstrap.sh` | Setup do ambiente de dev |
| `deploy.sh` | Deploy automatizado |
| `scripts/bump-version.sh` | Bump de versão |
| `scripts/provision_tenant.py` 🆕 | Provisiona tenant + schema + PBX |
| `scripts/setup-recording-mvp.sh` 🆕 | Setup do MVP de gravação |

## Convenção de nomes (política obrigatória — 2026-07)

Todo recurso Docker do projeto usa prefixo próprio, para não colidir com os outros stacks
que dividem o host de deploy (`sre_*`, `hermes*`, `freeswitch`, `portainer`):

| Recurso | Prefixo | Exemplo |
|---|---|---|
| Containers | `zenith-` | `zenith-api-1`, `zenith-arq-uploader`, `zenith-ip-watcher` |
| Volumes / networks | `zenith_` | `zenith_recordings_tmpfs`, `zenith_ollama_data` |
| Imagens locais | `zenith-` | `zenith-voip-freeswitch:latest` |

## Topologia Docker

### Infraestrutura (docker-compose.infra.yml)
- PostgreSQL 16-alpine (host 5433 → container 5432)
- Redis 7-alpine com appendonly (sem porta no host, só rede bridge)
- Prometheus v2.55.1 (host 9091), Grafana 11.3.0 (host 3002), Loki 3.2.1 (host 3102)

### Aplicação (docker-compose.app.yml)

| Container | Situação | Observação |
|---|---|---|
| `zenith-freeswitch` | 🔄 **build próprio** | Era `safarov/freeswitch:1.10.12`. Agora `build: ./freeswitch`, com secret `signalwire_token` e healthcheck próprio |
| `zenith-api-1` | 🔄 | Porta publicada agora só em `127.0.0.1:8001`; monta tmpfs de gravações; único que conecta ao ESL |
| `zenith-api-2` | 🔄 | Idem, em `127.0.0.1:8002` |
| `zenith-arq-uploader` | 🆕 | `arq src.workers.audio_uploader.WorkerSettings` |
| `zenith-arq-cleanup` | 🔄 | Sem variáveis S3; `AUDIO_RETENTION_DAYS=0.0417` (~1 h) |
| `zenith-ip-watcher` | 🆕 | `network_mode: host`, monta `./freeswitch/conf` |
| `zenith-bunkerweb` | 🔄 | `API_WHITELIST_IP` atualizado para `172.21.0.0/16` |
| `zenith-ollama` | — | GPU opcional |
| `piper-tts` | ❌ **removido** | TTS passou a rodar in-process (ver `services`) |

### Infra de Rede
- Subnet: **172.21.0.0/16** (era 172.20.0.0/16 — mudou por colisão com outro stack no host)
- Bridge: `ai-hub-net`
- `FREESWITCH_ESL_HOST` acompanhou: `172.20.0.1` → **`172.21.0.1`**

### Volumes
- `zenith_ollama_data` — modelos do Ollama
- `zenith_recordings_tmpfs` 🆕 — **tmpfs de 512 MB**, montado em `/data/recordings` por
  `zenith-api-1`, `zenith-api-2`, `zenith-arq-uploader` e `zenith-arq-cleanup`.
  Gravação vive em RAM e some no restart — coerente com a retenção de ~1 h.

### Secrets
`signalwire_token` (arquivo `freeswitch/signalwire_token.txt`, **gitignored**, com
`.example` versionado) — necessário para o build do FreeSWITCH.

## Healthcheck do FreeSWITCH 🆕

```
fs_cli -x 'module_exists mod_audio_stream' | grep -q true
```
`start_period: 90s` porque o profile `upstream` carrega ~939 gateways no boot e pode não
aceitar comandos ESL nos primeiros segundos. O healthcheck genérico da imagem base não sabia
nada sobre módulos do projeto — a imagem chegou a rodar **24 h "healthy" em produção sem
`mod_audio_stream` carregado**, sem nenhum sinal (GAP-24).

## Configuração (src/config.py)

| Setting | Antes | Agora |
|---|---|---|
| `FREESWITCH_ESL_HOST` | `172.20.0.1` | `172.21.0.1` |
| `AUDIO_STREAM_CALLBACK_HOST` | — | 🆕 `127.0.0.1:8001` |
| `PIPER_TTS_URL` | `http://piper-tts:5000` | ❌ removido |
| `PIPER_VOICE_PATH` | — | 🆕 `audio/voices/pt_BR-faber-medium.onnx` |
| `AUDIO_RETENTION_DAYS` | `int = 90` | `float = 90` |
| `RECORDINGS_PATH` | — | 🆕 `/data/recordings` |
| `S3_ENDPOINT` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` / `S3_BUCKET_PREFIX` | presentes | ❌ removidos |

## Estratégia de Deploy

- `deploy.sh` suporta staging/production com tags Git
- Registro de revisões em `revisions.json`
- Health check pós-deploy (até 12 tentativas), rollback para versão anterior
- CI/CD: nenhum (deploy manual via script)

## Config FreeSWITCH

- SIP profiles: `internal` (5060), **`internal-5062`** 🆕, **`internal-7060`** 🆕,
  **`upstream.xml`** 🆕 + `upstream/upstream-{ext}.xml` por ramal
- `vars.xml` 🆕 — `local_ip_v4=auto`, `external_*_ip=$${local_ip}`, `domain`, `pbx_host`,
  `tenant_id`, `pbx_id`; inclui `vars-external-ip.xml` escrito pelo `ip-watcher`
- `acl.conf.xml`, `event_socket.conf.xml`, `sofia.conf.xml`, `directory/default.xml` 🆕
- Módulos: `mod_audio_fork` → **`mod_audio_stream`**, `mod_esl` → **`mod_event_socket`**

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Duas instâncias FastAPI para HA | `docker-compose.app.yml` | 🟢 |
| Sticky session via X-Call-ID (BunkerWeb) | `docker-compose.app.yml` | 🟢 |
| GPU reservada para Ollama | `docker-compose.app.yml` | 🟢 |
| FreeSWITCH em `network_mode: host` | `docker-compose.app.yml` | 🟢 |
| 🆕 Portas da API só em loopback do host | `docker-compose.app.yml` | 🟢 |
| 🆕 Gravações em tmpfs de 512 MB (RAM), não em disco | `docker-compose.app.yml` | 🟢 |
| 🆕 FreeSWITCH só é "healthy" se `mod_audio_stream` estiver carregado | `docker-compose.app.yml` | 🟢 |
| 🆕 Nenhum recurso Docker fora do prefixo `zenith-`/`zenith_` pode ser tocado | `CLAUDE.md` | 🟢 |

## Riscos abertos

| Risco | Nota |
|---|---|
| tmpfs de 512 MB | Não há backpressure: com muitas chamadas simultâneas o volume enche e a gravação falha silenciosamente |
| HA parcial | Só `fastapi-1` consome ESL; se cair, `fastapi-2` serve HTTP mas nada é gravado |
| `tenant_id`/`pbx_id` fixos no `vars.xml` | Multi-tenant real exige que venham do canal, não de variável global (hoje serve só o tenant Akom) |
