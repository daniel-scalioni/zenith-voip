# Plano de Deploy — Fase 1: FreeSWITCH B2BUA Registration Forwarding

**Data:** 2026-06-26
**Repositório:** https://github.com/daniel-scalioni/zenith-voip.git
**Commit base:** `ef93ae1` — "feat: implement FreeSWITCH bootstrap configuration and B2BUA registration forwarding infrastructure"
**Servidor:** `10.10.10.11` (SSH como `administrator`)
**Projeto no servidor:** `~/zenith-voip/`

---

## Contexto

O projeto **zenith-voip** implementa um hub de IA para chamadas VoIP. O FreeSWITCH atua como
**B2BUA (Back-to-Back User Agent)** posicionado entre os interfones/softphones da empresa e o
PBX de produção (VitalPBX / GPhone em `sip.maisalerta.tecnorise.com`).

**O que foi feito antes deste deploy:**
- FreeSWITCH já está rodando no servidor (`docker compose -f docker-compose.app.yml up -d freeswitch`)
- A imagem usada é `safarov/freeswitch:1.10.12` (vanilla, sem `mod_audio_fork`)
- O container monta `./freeswitch/conf/` em `/etc/freeswitch/` (volume bind mount)

**O que este deploy adiciona:**
1. Profile SIP `upstream` (porta 5065) — gateway de saída para o VitalPBX
2. Variável `pbx_host=sip.maisalerta.tecnorise.com` no `vars.xml`
3. 939 gateways upstream (um por ramal) para o FreeSWITCH se registrar no VitalPBX
4. 939 entradas de usuário no diretório para autenticar os interfones localmente
5. `directory/default.xml` atualizado para incluir o arquivo de usuários gerado

**Arquitetura resumida:**
```
Interfone → REGISTER (ext=1001, senha) → FreeSWITCH porta 5060
FreeSWITCH → REGISTER (ext=1001, mesma senha) → VitalPBX sip.maisalerta.tecnorise.com
VitalPBX enxerga o ramal 1001 como registrado (via FreeSWITCH)
```

---

## Arquivos no repositório (git clone/pull)

Estes arquivos estão no GitHub e chegam via `git pull`:

| Arquivo | O que faz |
|---------|-----------|
| `freeswitch/conf/vars.xml` | Variáveis globais — inclui `pbx_host` |
| `freeswitch/conf/sip_profiles/upstream.xml` | Profile SIP upstream (sem credenciais) |
| `freeswitch/conf/directory/default.xml` | Inclui `extensions.xml` via X-PRE-PROCESS |
| `freeswitch/conf/sip_profiles/internal.xml` | Corrigido: sem TLS, porta 5060 apenas |
| `freeswitch/conf/dialplan/default.xml` | Regras de roteamento local e echo test |
| `scripts/import_extensions.py` | Script de importação em lote do CSV |

## Arquivos com credenciais (NÃO estão no git — cópia manual)

Estes arquivos contêm senhas SIP e estão gitignored:

| Arquivo | O que faz |
|---------|-----------|
| `freeswitch/conf/directory/extensions.xml` | 939 usuários com senha para auth local |
| `freeswitch/conf/sip_profiles/upstream/*.xml` | 939 gateways com senha para upstream |

**Origem dos arquivos de credenciais:**
- Foram gerados localmente pelo script `scripts/import_extensions.py` a partir do CSV
  exportado do VitalPBX (`specs/export_extensions.csv`)
- Estão disponíveis na sessão Claude Code em `/app/zenith-voip/`
- Precisam ser copiados para o servidor via `scp`

---

## Pré-requisitos

Antes de começar, confirmar:

- [ ] Acesso SSH ao servidor: `ssh administrator@10.10.10.11`
- [ ] Git instalado no servidor: `git --version`
- [ ] Docker e docker-compose disponíveis no servidor: `docker --version`
- [ ] Container `freeswitch` está rodando: `docker ps | grep freeswitch`

---

## Passo 1 — Configurar git no servidor (primeira vez)

O diretório `~/zenith-voip/` existe no servidor mas **não é um repositório git**.
Execute no servidor:

```bash
cd ~/zenith-voip

# Inicializar git
git init
git remote add origin https://github.com/daniel-scalioni/zenith-voip.git

# Baixar o repositório
git fetch origin

# Criar branch local main rastreando o remote
git checkout -b main --track origin/main
```

**Se o checkout reclamar de arquivos existentes (conflito):**
```bash
# Verificar quais arquivos conflitam
git status

# Forçar checkout (atenção: sobrescreve arquivos locais NÃO commitados)
# Antes, certifique-se que .env e outros arquivos sensíveis locais estão seguros
git checkout -f main
```

**Verificar resultado esperado:**
```bash
git log --oneline -3
# Deve mostrar: ef93ae1 feat: implement FreeSWITCH bootstrap configuration...
```

---

## Passo 2 — Copiar arquivos de credenciais para o servidor

Estes comandos devem ser executados **na sessão Claude Code** (ambiente local, `/app/zenith-voip/`),
pois é onde os arquivos com senhas existem:

```bash
# Copiar o arquivo de usuários do diretório
scp /app/zenith-voip/freeswitch/conf/directory/extensions.xml \
    administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/directory/

# Criar pasta upstream no servidor (pode já existir após o git pull)
ssh administrator@10.10.10.11 "mkdir -p ~/zenith-voip/freeswitch/conf/sip_profiles/upstream"

# Copiar os 939 gateways
scp -r /app/zenith-voip/freeswitch/conf/sip_profiles/upstream/ \
    administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/sip_profiles/
```

**Verificar no servidor:**
```bash
ssh administrator@10.10.10.11 \
  "ls ~/zenith-voip/freeswitch/conf/directory/extensions.xml && \
   ls ~/zenith-voip/freeswitch/conf/sip_profiles/upstream/ | wc -l"
# Deve mostrar: o caminho do extensions.xml e o número 939
```

---

## Passo 3 — Reiniciar o FreeSWITCH

No servidor:

```bash
cd ~/zenith-voip
docker compose -f docker-compose.app.yml restart freeswitch
```

Aguardar 30 segundos para o FreeSWITCH carregar os perfis e iniciar os registros upstream.

---

## Passo 4 — Validação

**4.1 Verificar se o container subiu sem erros:**
```bash
docker compose -f docker-compose.app.yml ps freeswitch
# Esperado: Status = running, RestartCount = 0

docker compose -f docker-compose.app.yml logs --tail=30 freeswitch
# Não deve ter: "ERROR", "CRIT", "mod_sofia could not be loaded"
# Deve ter: "FreeSWITCH Started", "sofia profile internal started"
```

**4.2 Verificar os perfis SIP:**
```bash
docker exec freeswitch fs_cli -x "sofia status"
# Esperado: profiles "internal" e "upstream" listados, ambos com status RUNNING
```

**4.3 Verificar um gateway específico:**
```bash
docker exec freeswitch fs_cli -x "sofia status gateway upstream-1001"
# Esperado: STATUS = REGED (registered) ou TRYING
# Se NOREG/FAIL: o VitalPBX rejeitou as credenciais do ramal 1001
```

**4.4 Contar quantos gateways estão registrados:**
```bash
docker exec freeswitch fs_cli -x "sofia status gateway" | grep -c REGED
# Esperado: número próximo a 939 após alguns minutos
# Os registros ocorrem em ondas — aguardar 2-3 minutos para todos subirem
```

**4.5 Verificar se um usuário está no diretório:**
```bash
docker exec freeswitch fs_cli -x "user_data 1001 attr password"
# Esperado: a senha SIP do ramal 1001 (string não vazia)
```

**4.6 Teste de eco (registrar um softphone):**
- Configure um softphone (Zoiper, Linphone, MicroSIP) com:
  - Servidor: `10.10.10.11`
  - Porta: `5060`
  - Usuário: número do ramal (ex: `1001`)
  - Senha: senha SIP do ramal (a mesma do GPhone)
  - Domínio: `zenith.local`
- Após registrar, disque `9196` → deve ouvir eco (confirma registro + dialplan OK)

---

## Passo 5 — Deploy futuros (após git estar configurado no servidor)

A partir de agora, atualizações de código (sem credenciais) são simples:

```bash
# No servidor
cd ~/zenith-voip && git pull
docker compose -f docker-compose.app.yml restart freeswitch
```

Para atualizar as credenciais (novo lote de ramais):
1. Exportar CSV atualizado do VitalPBX
2. Na sessão Claude Code: `python3 scripts/import_extensions.py specs/export_extensions.csv`
3. Copiar os arquivos gerados para o servidor (Passo 2 acima)
4. Reload dos gateways sem restart: `docker exec freeswitch fs_cli -x "sofia profile upstream rescan"`

---

## Rollback

Se o FreeSWITCH não subir corretamente após o deploy:

```bash
# No servidor — ver logs detalhados
docker compose -f docker-compose.app.yml logs freeswitch 2>&1 | tail -50

# Reverter para o commit anterior
cd ~/zenith-voip && git checkout 4a724e4 -- freeswitch/conf/
docker compose -f docker-compose.app.yml restart freeswitch
```

---

## Problemas conhecidos e soluções

| Sintoma | Causa provável | Solução |
|---------|---------------|---------|
| Profile `upstream` não aparece em `sofia status` | `upstream.xml` não chegou no servidor | Verificar git pull + arquivo existe |
| Gateway `upstream-XXXX` com status `FAIL` | Credenciais incorretas para esse ramal | Verificar senha no VitalPBX |
| `user_data 1001 attr password` retorna vazio | `extensions.xml` não foi copiado | Repetir Passo 2 |
| FreeSWITCH reiniciando (Restarting no `docker ps`) | Erro de sintaxe nos XMLs gerados | Ver logs; verificar `extensions.xml` com `xmllint --noout` |
| Softphone registra mas não ouve eco no 9196 | Dialplan não carregou | `fs_cli -x "reloadxml"` |
