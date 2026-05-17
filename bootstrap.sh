#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# bootstrap.sh — Zenish AI Audio Hub
# Setup automatizado do ambiente de desenvolvimento
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Zenith AI Audio Hub — Bootstrap ==="

# ── 1. Verificar dependências ──────────────────────────────
echo "[1/6] Verificando dependências..."

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 não encontrado"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker não encontrado"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "ERROR: docker compose não encontrado"; exit 1; }

echo "  ✓ python3 $(python3 --version 2>&1 | awk '{print $2}')"
echo "  ✓ docker $(docker --version 2>&1 | awk '{print $3}' | tr -d ',')"
echo "  ✓ docker compose $(docker compose version 2>&1 | awk '{print $4}')"

# ── 2. Criar .env ─────────────────────────────────────────
echo "[2/6] Criando .env a partir de .env.example..."
if [ -f .env ]; then
  echo "  → .env já existe, preservando"
else
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "  ✓ .env criado de .env.example"
  else
    cat > .env << 'ENVEOF'
DEEPGRAM_API_KEY=
OPENAI_API_KEY=
INSTANCE_ID=1
REDIS_URL=redis://redis:6379/0
DATABASE_URL=postgresql+asyncpg://zenith:zenith@postgres:5432/zenith
FREESWITCH_ESL_HOST=172.20.0.1
FREESWITCH_ESL_PORT=8021
OLLAMA_URL=http://ollama:11434
JWT_SECRET=change-me-in-production
LOG_LEVEL=INFO
ENVEOF
    echo "  ✓ .env criado (preencha DEEPGRAM_API_KEY se necessário)"
  fi
fi

# ── 3. Python venv ─────────────────────────────────────────
echo "[3/6] Configurando ambiente Python..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
  echo "  ✓ virtualenv criado em .venv"
fi

source .venv/bin/activate
pip install --quiet --upgrade pip setuptools wheel
pip install --quiet -r requirements.txt
echo "  ✓ dependências Python instaladas"

# Download spaCy model
python3 -m spacy download pt_core_news_sm 2>/dev/null || echo "  ⚠ spacy pt model: será baixado na primeira execução"

# ── 4. Configurar FreeSWITCH ──────────────────────────────
echo "[4/6] Gerando configurações FreeSWITCH..."
mkdir -p freeswitch/conf

# Testar conexão SIP (se PBX estiver acessível)
PBX_HOST="${PBX_HOST:-192.168.1.1}"
PBX_PORT="${PBX_PORT:-5060}"
if command -v nc &>/dev/null; then
  if nc -z -w2 "$PBX_HOST" "$PBX_PORT" 2>/dev/null; then
    echo "  ✓ PBX reachable at $PBX_HOST:$PBX_PORT"
  else
    echo "  ⚠ PBX $PBX_HOST:$PBX_PORT not reachable (expected if offline)"
  fi
fi

# ── 5. Docker Compose up ──────────────────────────────────
echo "[5/6] Iniciando containers..."
docker compose up --build -d
echo "  ✓ Containers iniciados"
echo "  → FastAPI-1: http://localhost:8001/health"
echo "  → FastAPI-2: http://localhost:8002/health"
echo "  → BunkerWeb: http://localhost:80"
echo "  → Grafana:   http://localhost:3000 (admin/zenith)"
echo "  → Prometheus: http://localhost:9090"
echo "  → Redis:     localhost:6379"

# ── 6. Health check ───────────────────────────────────────
echo "[6/6] Health check inicial..."
sleep 5
for i in 1 2; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:800${i}/health" 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "  ✓ FastAPI-$i healthy (HTTP $STATUS)"
  else
    echo "  ⚠ FastAPI-$i HTTP $STATUS (pode estar ainda subindo)"
  fi
done

echo ""
echo "=== Bootstrap concluído ==="
echo "Execute 'docker compose logs -f' para acompanhar os logs."
