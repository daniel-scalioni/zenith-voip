#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# setup-recording-mvp.sh — Zenith VoIP
# Provisiona a infra do MVP de gravação: FreeSWITCH com mod_audio_fork
# (GAP-11) + storage local de gravação + workers (GAP-14/GAP-15).
# Mesmo padrão de helpers de deploy.sh.
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
cd "$PROJECT_DIR"

APP_COMPOSE="docker-compose.app.yml"
INFRA_COMPOSE="docker-compose.infra.yml"
SIGNALWIRE_TOKEN_FILE="freeswitch/signalwire_token.txt"
RECORDINGS_DIR="data/recordings"

# ── Utils (mesmo estilo de deploy.sh) ───────────────────────────
color() { echo -e "\e[${1}m${2}\e[0m"; }
green()  { color 32 "$1"; }
yellow() { color 33 "$1"; }
red()    { color 31 "$1"; }
cyan()   { color 36 "$1"; }

info()    { echo -e "$(cyan '→') $1"; }
success() { echo -e "$(green '✓') $1"; }
warn()    { echo -e "$(yellow '⚠') $1"; }
error()   { echo -e "$(red '✘') $1"; }

die() {
    error "$1"
    exit 1
}

check_docker() {
    if ! docker info >/dev/null 2>&1; then
        die "Docker não está rodando. Verifique o serviço Docker."
    fi
    if ! docker compose version >/dev/null 2>&1; then
        die "docker compose não encontrado."
    fi
    success "Docker disponível."
}

check_signalwire_token() {
    if [[ ! -f "$SIGNALWIRE_TOKEN_FILE" ]]; then
        die "Faltando $SIGNALWIRE_TOKEN_FILE. Crie sua conta em https://id.signalwire.com/signup/account/new, copie o token e siga as instruções em ${SIGNALWIRE_TOKEN_FILE}.example."
    fi
    success "Token SignalWire encontrado."
}

health_check() {
    local max_attempts=12
    local attempt=1

    info "Aguardando health check das APIs..."
    while [[ $attempt -le $max_attempts ]]; do
        local ok=true
        for port in 8001 8002; do
            local status
            status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port/health" 2>/dev/null || echo "000")
            if [[ "$status" != "200" ]]; then
                ok=false
                break
            fi
        done
        if $ok; then
            success "Ambas as APIs respondendo (8001, 8002)."
            return 0
        fi
        sleep 5
        attempt=$((attempt + 1))
    done

    error "Health check falhou após ${max_attempts} tentativas."
    return 1
}

check_audio_fork_loaded() {
    info "Verificando se mod_audio_fork carregou no FreeSWITCH..."
    if docker logs freeswitch 2>&1 | grep -qi "mod_audio_fork"; then
        if docker logs freeswitch 2>&1 | grep -qi "mod_audio_fork.*\(error\|cannot open\|fail\)"; then
            warn "mod_audio_fork apareceu no log com indício de erro — revise 'docker logs freeswitch'."
        else
            success "mod_audio_fork referenciado no log de boot sem erro aparente."
        fi
    else
        warn "Nenhuma menção a mod_audio_fork no log do FreeSWITCH — confirme manualmente com 'docker logs freeswitch'."
    fi
}

# ── Main ─────────────────────────────────────────────────────────

echo ""
cyan "═══════════════════════════════════════════════"
cyan "  Setup MVP de Gravação — Zenith VoIP"
cyan "═══════════════════════════════════════════════"
echo ""

check_docker
check_signalwire_token

info "Criando diretório de gravações em ./${RECORDINGS_DIR}..."
mkdir -p "$RECORDINGS_DIR"
success "Diretório pronto."

info "Subindo infraestrutura (postgres, redis)..."
docker compose -f "$INFRA_COMPOSE" up -d --wait
success "Infraestrutura no ar."

info "Construindo imagens (inclui build do FreeSWITCH com mod_audio_fork)..."
docker compose -f "$APP_COMPOSE" build
success "Imagens construídas."

info "Executando migrations..."
docker compose -f "$APP_COMPOSE" run --rm fastapi-1 alembic upgrade head
success "Migrations concluídas."

info "Subindo FreeSWITCH, FastAPI e workers..."
docker compose -f "$APP_COMPOSE" up -d freeswitch fastapi-1 fastapi-2 arq-uploader arq-cleanup
success "Containers no ar."

check_audio_fork_loaded

if health_check; then
    echo ""
    green "═══════════════════════════════════════════════"
    green "  ✅ Infra do MVP de gravação pronta"
    green "═══════════════════════════════════════════════"
else
    warn "Containers no ar, mas health check falhou. Verifique 'docker compose -f $APP_COMPOSE logs'."
fi

echo ""
cyan "Próximos passos manuais (não automatizáveis por aqui):"
echo "  1. Originar uma chamada de teste contra a extensão zenith_audio_fork."
echo "  2. Confirmar Call 'completed' no Postgres após o hangup."
echo "  3. Conferir ./${RECORDINGS_DIR}/{tenant_id}/{call_id}/{tx,rx}.raw."
echo "  4. Ouvir os dois arquivos e validar se a convenção tx=agente/rx=cliente"
echo "     está correta (se estiver invertida, trocar em"
echo "     src/audio/ingestor.py::AudioIngestor._split_stereo_frame)."
