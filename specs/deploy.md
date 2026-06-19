# Plano de Deploy — Zenith AI Audio Hub

> **Projeto:** Zenith VoIP — AI Audio Hub
> **Feature:** 001-ai-audio-hub
> **Data:** 2026-05-17

---

## Antes de começar — configure estas variáveis

Edite os arquivos abaixo com os valores do seu ambiente **antes** de subir os containers:

| Arquivo | O que ajustar |
|---------|---------------|
| `freeswitch/conf/dialplan/default.xml` | `${pbx_host}` → IP do PBX real |
| `freeswitch/conf/sip_profiles/internal.xml` | `$${external_rtp_ip}` e `$${external_sip_ip}` → IP da máquina Windows |
| `.env` | `DEEPGRAM_API_KEY`, `JWT_SECRET` |

> O `.env` já existe no volume compartilhado. Edite-o no Windows ou peça para eu ajustar aqui no container.

---

## Visão geral dos ambientes

```
┌─────────────────────────────────────────────────────────────┐
│ WINDOWS (D:\projetos\Projetos\zenith-voip\)                 │
│  - Docker Desktop                                           │
│  - docker compose up / down / logs                          │
│  - NÃO tem Python, NÃO tem Rust, NÃO tem dev tools          │
│  - Apenas gerencia containers                               │
└──────────────────────┬──────────────────────────────────────┘
                       │ bind mount (mesmos arquivos)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ CONTAINER DEV (ubuntu)                                      │
│  - /app/Projetos/zenith-voip/ ←→ D:\projetos\Projetos\...  │
│  - Python + .venv + bibliotecas                             │
│  - pytest, alembic, scripts                                 │
│  - Tudo que precisar instalar, instala AQUI                 │
└─────────────────────────────────────────────────────────────┘
```

> Qualquer alteração salva no container reflete no Windows e vice-versa (volume espelhado).

---

## Setup inicial (única vez)

Tudo que precisa de instalação roda **no container dev**. No Windows nada é instalado além do Docker.

```bash
# Executar DENTRO DO CONTAINER DEV:

# 1. Criar .env com valores padrão (se não existir)
cat > .env << 'EOF'
DEEPGRAM_API_KEY=
JWT_SECRET=change-me-in-production
LOG_LEVEL=INFO
REDIS_URL=redis://redis:6379/0
DATABASE_URL=postgresql+asyncpg://zenith:zenith@postgres:5432/zenith
FREESWITCH_ESL_HOST=172.20.0.1
FREESWITCH_ESL_PORT=8021
OLLAMA_URL=http://ollama:11434
PIPER_TTS_URL=http://piper-tts:5000
EOF

# 2. Instalar dependências Python
pip install -r requirements.txt

# 3. Baixar modelo spaCy
python -m spacy download pt_core_news_sm
```

---

## Subir containers (no Windows, PowerShell)

```powershell
# Navegar até a pasta do projeto
cd D:\projetos\Projetos\zenith-voip

# ── Passo 1: Infraestrutura ─────────────────────────────
docker compose up -d postgres redis prometheus grafana loki

# ── Passo 2: Migrations ─────────────────────────────────
docker compose run --rm fastapi-1 alembic upgrade head

# ── Passo 3: Serviços de IA ─────────────────────────────
docker compose up -d ollama piper-tts
# Aguardar ~2min para o Ollama iniciar
# Baixar modelo:
docker compose exec ollama ollama pull mistral:7b

# ── Passo 4: Backend FastAPI ────────────────────────────
docker compose up -d fastapi-1 fastapi-2 --build

# ── Passo 5: FreeSWITCH ─────────────────────────────────
docker compose up -d freeswitch

# ── Passo 6: BunkerWeb ──────────────────────────────────
docker compose up -d bunkerweb
```

---

## Verificar se tudo está rodando

```powershell
# Status geral
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# Health checks
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:9090

# Teste Redis Streams
docker compose exec redis redis-cli XADD test:stream * event ping
docker compose exec redis redis-cli XREAD COUNT 1 STREAMS test:stream 0
docker compose exec redis redis-cli DEL test:stream
```

Resposta esperada do health:
```json
{"status":"ok","instance_id":1}
{"status":"ok","instance_id":2}
```

---

## Rodar testes (no container dev)

```bash
# Executar DENTRO DO CONTAINER DEV
source .venv/bin/activate

# Testes unitários (não precisam de containers)
pytest tests/ -v --timeout=30

# Testes específicos
pytest tests/test_infra.py -v
pytest tests/test_freeswitch_esl.py -v
pytest tests/test_bunker_sticky.py -v
```

> Testes que dependem de containers (ESL, BunkerWeb) só funcionam com os containers rodando no Windows.

---

## Build do Widget Tauri (opcional)

O Tauri requer Rust + WebView2 — instale **no container dev** (não no Windows).

```bash
# No container dev:
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
cd widget
npm install
npx tauri build
# O .exe será gerado em widget/src-tauri/target/release/
# (visível no Windows via volume compartilhado)
```

---

## Comandos úteis do dia-a-dia (PowerShell)

```powershell
# Ver logs de um serviço
docker compose logs -f fastapi-1

# Rebuild de um serviço após alteração de código
docker compose up -d fastapi-1 --build

# Parar tudo
docker compose down

# Parar e limpar volumes (cuidado: apaga dados do banco)
docker compose down -v

# Acessar o banco
docker compose exec postgres psql -U zenith -d zenith

# Acessar o Redis CLI
docker compose exec redis redis-cli
```

---

## Mapa de portas (localhost)

| Porta | Serviço | Acesso |
|-------|---------|--------|
| 8001 | FastAPI instância 1 | `http://localhost:8001/health` |
| 8002 | FastAPI instância 2 | `http://localhost:8002/health` |
| 80 | BunkerWeb WAF | `http://localhost:80` |
| 5432 | PostgreSQL | `localhost:5432` (zenith/zenith) |
| 6379 | Redis | `localhost:6379` |
| 11434 | Ollama | `http://localhost:11434` |
| 5000 | Piper TTS | `http://localhost:5000` |
| 9090 | Prometheus | `http://localhost:9090` |
| 3000 | Grafana | `http://localhost:3000` (admin/zenith) |
| 3100 | Loki | `http://localhost:3100` |
| 5060 | FreeSWITCH SIP | `network_mode: host` |
| 8021 | FreeSWITCH ESL | `localhost:8021` (pass: ClueCon) |

---

## Troubleshooting

| Problema | Causa | Solução |
|----------|-------|---------|
| FastAPI não sobe | DB não está pronto | Aguardar health check do PostgreSQL |
| Ollama lento | Sem GPU | Usar modelo quantizado (q4_K_M) |
| FreeSWITCH não registra no PBX | IP errado no dialplan | Ajustar `${pbx_host}` em `default.xml` |
| BunkerWeb 502 | FastAPI não responde | `docker compose logs fastapi-1` |
| ESL connection refused | FS ainda subindo | Aguardar 10s e tentar de novo |
| Porta já em uso | Outro serviço na mesma porta | Parar o conflitante ou mudar a porta no `.env` |
