#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# deploy.sh — Zenith AI Audio Hub
# Deploy automatizado com controle de revisões
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Config ────────────────────────────────────────────────────
APP_COMPOSE="docker-compose.app.yml"
INFRA_COMPOSE="docker-compose.infra.yml"
REVISIONS_FILE="revisions.json"
APP_SERVICES=("freeswitch" "fastapi-1" "fastapi-2" "arq-cleanup" "bunkerweb" "ollama" "piper-tts")

# ── Help ──────────────────────────────────────────────────────
usage() {
    echo "Zenith VoIP — Deploy Automatizado"
    echo ""
    echo "Uso:"
    echo "  $0 staging <tag>         Deploy da tag no ambiente staging"
    echo "  $0 production <tag>       Deploy da tag no ambiente production"
    echo "  $0 status                 Exibe versões ativas em cada ambiente"
    echo "  $0 rollback <env>         Reverte para a versão anterior"
    echo "  $0 -h                     Ajuda"
    echo ""
    echo "Exemplos:"
    echo "  $0 staging v1.1.0"
    echo "  $0 rollback staging"
    echo "  $0 status"
    exit 1
}

# ── Utils ─────────────────────────────────────────────────────
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

confirm() {
    echo ""
    read -r -p "$(yellow "? $1 [s/N] ")" REPLY
    [[ "$REPLY" =~ ^[sSyY] ]]
}

# ── Helpers ───────────────────────────────────────────────────
validate_env() {
    local env="$1"
    if [[ "$env" != "staging" && "$env" != "production" ]]; then
        die "Ambiente inválido: '$env'. Use 'staging' ou 'production'."
    fi
}

env_file() {
    echo ".env.$1"
}

check_docker() {
    if ! docker info >/dev/null 2>&1; then
        die "Docker não está rodando. Verifique o serviço Docker."
    fi
    if ! docker compose version >/dev/null 2>&1; then
        die "docker compose não encontrado."
    fi
}

check_infra() {
    local infra_services
    infra_services=$(docker compose -f "$INFRA_COMPOSE" ps --services --filter "status=running" 2>/dev/null || echo "")
    if [[ -z "$infra_services" ]]; then
        warn "Nenhum serviço de infraestrutura detectado."
        warn "Execute primeiro: docker compose -f $INFRA_COMPOSE up -d"
        if ! confirm "Continuar mesmo assim?"; then
            die "Deploy abortado."
        fi
    else
        success "Infraestrutura rodando: $(echo "$infra_services" | tr '\n' ' ')"
    fi
}

detect_impacted_services() {
    local running
    running=$(docker compose -f "$APP_COMPOSE" ps --services --filter "status=running" 2>/dev/null || echo "")
    if [[ -n "$running" ]]; then
        warn "Este deploy vai recriar os containers:"
        echo "$running" | while read -r svc; do
            echo "    - $svc"
        done
        echo ""
        if ! confirm "Prosseguir com o deploy?"; then
            die "Deploy abortado pelo usuário."
        fi
    fi
}

check_env_file() {
    local env="$1"
    local file
    file=$(env_file "$env")
    if [[ ! -f "$file" ]]; then
        die "Arquivo $file não encontrado. Crie a partir de $file.example."
    fi
    success "Arquivo $file encontrado."
}

check_git_tag() {
    local tag="$1"
    if ! git rev-parse "$tag" >/dev/null 2>&1; then
        die "Tag '$tag' não encontrada. Faça fetch primeiro: git fetch --tags"
    fi
    success "Tag '$tag' encontrada."
}

record_revision() {
    local env="$1"
    local tag="$2"
    local status="${3:-active}"
    local date
    date=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    local tmp
    tmp=$(mktemp)

    if [[ -f "$REVISIONS_FILE" ]]; then
        python3 -c "
import json, sys
with open('$REVISIONS_FILE') as f:
    data = json.load(f)
env_data = data.get('$env', {'current': None, 'history': []})
if '$status' == 'active':
    # Mark previous active as rolled_back
    for entry in env_data['history']:
        if entry['status'] == 'active':
            entry['status'] = 'rolled_back'
    env_data['current'] = '$tag'
env_data['history'].append({
    'version': '$tag',
    'date': '$date',
    'status': '$status'
})
data['$env'] = env_data
with open('$tmp', 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null || {
        warn "Falha ao registrar revisão (python3 não disponível). Salvando formato simples."
        echo "{\"$env\": {\"current\": \"$tag\", \"history\": [{\"version\": \"$tag\", \"date\": \"$date\", \"status\": \"$status\"}]}}" > "$tmp"
    }
    else
        echo "{\"$env\": {\"current\": \"$tag\", \"history\": [{\"version\": \"$tag\", \"date\": \"$date\", \"status\": \"$status\"}]}}" > "$tmp"
    fi

    mv "$tmp" "$REVISIONS_FILE"
    success "Revisão registrada: $tag ($env, $status)"
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

# ── Commands ──────────────────────────────────────────────────

cmd_deploy() {
    local env="$1"
    local tag="$2"
    local env_file_path
    env_file_path=$(env_file "$env")

    echo ""
    cyan "═══════════════════════════════════════════════"
    cyan "  Deploy: $env ← $tag"
    cyan "═══════════════════════════════════════════════"
    echo ""

    validate_env "$env"
    check_docker
    check_git_tag "$tag"
    check_env_file "$env"
    check_infra
    detect_impacted_services

    # ── Checkout ──
    info "Fazendo checkout de $tag..."
    git checkout "$tag"
    success "Checkout concluído."

    # ── Select env file ──
    cp "$env_file_path" .env
    success "Usando $env_file_path → .env"

    # ── Build ──
    info "Construindo imagens..."
    docker compose -f "$APP_COMPOSE" build
    success "Imagens construídas."

    # ── Migrations ──
    info "Executando migrations..."
    docker compose -f "$APP_COMPOSE" run --rm fastapi-1 alembic upgrade head
    success "Migrations concluídas."

    # ── Deploy ──
    info "Subindo containers da aplicação..."
    docker compose -f "$APP_COMPOSE" up -d
    success "Containers da aplicação no ar."

    # ── Health check ──
    if health_check; then
        record_revision "$env" "$tag" "active"
        echo ""
        green "═══════════════════════════════════════════════"
        green "  ✅ Deploy concluído: $env = $tag"
        green "═══════════════════════════════════════════════"
    else
        warn "Deploy concluído, mas health check falhou. Verifique os logs."
        record_revision "$env" "$tag" "degraded"
    fi
}

cmd_status() {
    echo ""
    cyan "═══════════════════════════════════════════════"
    cyan "  Status dos Ambientes"
    cyan "═══════════════════════════════════════════════"
    echo ""

    if [[ ! -f "$REVISIONS_FILE" ]]; then
        warn "Nenhum deploy registrado ainda. ($REVISIONS_FILE não encontrado)"
        return
    fi

    python3 -c "
import json
with open('$REVISIONS_FILE') as f:
    data = json.load(f)

for env in ['staging', 'production']:
    env_data = data.get(env, {'current': None, 'history': []})
    current = env_data.get('current', '—')
    history = env_data.get('history', [])

    print(f'  {env.upper()}:')
    print(f'    Atual:  {current}')
    print(f'    Total de revisões: {len(history)}')

    # Last 3 revisions
    if history:
        print('    Últimas:')
        for entry in history[-3:]:
            v = entry.get('version', '?')
            d = entry.get('date', '?')[:10]
            s = entry.get('status', '?')
            icon = {'active': '✅', 'rolled_back': '⏪', 'degraded': '⚠️'}.get(s, '❓')
            print(f'      {icon} {v} ({d}) — {s}')
    print()
" 2>/dev/null || {
        warn "python3 não disponível. Exibindo raw:"
        cat "$REVISIONS_FILE"
    }
}

cmd_rollback() {
    local env="$1"
    validate_env "$env"

    echo ""
    cyan "═══════════════════════════════════════════════"
    cyan "  Rollback: $env"
    cyan "═══════════════════════════════════════════════"
    echo ""

    if [[ ! -f "$REVISIONS_FILE" ]]; then
        die "Nenhum histórico de revisões encontrado."
    fi

    # Find previous active version
    local prev_tag
    prev_tag=$(python3 -c "
import json
with open('$REVISIONS_FILE') as f:
    data = json.load(f)
env_data = data.get('$env', {'history': []})
history = env_data.get('history', [])
# Find the last 'active' entry before current
active_found = False
for entry in reversed(history):
    if entry['status'] == 'active':
        if not active_found:
            active_found = True  # skip current
            continue
        print(entry['version'])
        break
" 2>/dev/null || true)

    if [[ -z "$prev_tag" ]]; then
        die "Nenhuma versão anterior encontrada para $env."
    fi

    info "Revertendo $env para $prev_tag..."
    if confirm "Confirma o rollback para $prev_tag?"; then
        cmd_deploy "$env" "$prev_tag"
        success "Rollback concluído: $env → $prev_tag"
    else
        die "Rollback abortado."
    fi
}

# ── Main ──────────────────────────────────────────────────────

if [[ $# -lt 1 ]]; then
    usage
fi

CMD="${1:-}"

case "$CMD" in
    staging|production)
        if [[ $# -lt 2 ]]; then
            die "Uso: $0 $CMD <tag>"
        fi
        cmd_deploy "$CMD" "$2"
        ;;
    status)
        cmd_status
        ;;
    rollback)
        if [[ $# -lt 2 ]]; then
            die "Uso: $0 rollback <staging|production>"
        fi
        cmd_rollback "$2"
        ;;
    -h|--help)
        usage
        ;;
    *)
        usage
        ;;
esac
