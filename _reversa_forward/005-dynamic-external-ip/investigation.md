# Investigation: Detecção Dinâmica de IP Externo

> Feature: `005-dynamic-external-ip`
> Data: `2026-06-29`

## Alternativas avaliadas

### 1. Descoberta de IP público

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| STUN (stun.freeswitch.org) | Protocolo padrão para descoberta de IP público em SIP | UDP 3478 bloqueado no firewall do CPD; cliente mantém STUN desativado | ❌ |
| HTTP (ifconfig.me) | Simples, funciona em qualquer rede com HTTP | Depende de serviço externo de terceiros | ❌ |
| HTTP (endpoint DNS próprio) | Controlado pelo cliente, sem dependência externa, aponta para o IP do CPD | Requer configurar o endpoint | ✅ |
| Source IP do socket FreeSWITCH | Zero dependência externa, sempre correto | Pode não refletir IP público se houver NAT em cascata | Fallback ✅ |

### 2. Local do watcher

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Container sidecar | Isolado, sem modificar FreeSWITCH, portável | +1 container no compose | ✅ |
| Script no entrypoint do FreeSWITCH | Sem container extra | Exige build customizado (viola RF-06) | ❌ |
| Cron no host Docker | Zero overhead de container | Quebra portabilidade, fora do Docker Compose | ❌ |
| Módulo nativo do FreeSWITCH (mod_curl) | Zero dependência externa | Exige build customizado; sem lógica de polling nativa | ❌ |

### 3. Mecanismo de atualização no FreeSWITCH

Variáveis `$${...}` no FreeSWITCH são pré-processadas (compile-time) em cada `reloadxml`. Isso significa que `reloadxml` re-lê o `vars.xml` do disco — se o arquivo ainda contiver `external_sip_ip=$${local_ip}`, o IP privado volta a ser baked in. **É obrigatório gravar o novo IP em disco antes de chamar `reloadxml`.**

**Mecanismo adotado — arquivo include:**

1. O sidecar escreve `/etc/freeswitch/vars-external-ip.xml` com o IP novo:
   ```xml
   <include>
     <X-PRE-PROCESS cmd="set" data="external_sip_ip=X.X.X.X"/>
     <X-PRE-PROCESS cmd="set" data="external_rtp_ip=X.X.X.X"/>
   </include>
   ```
2. O `vars.xml` inclui esse arquivo logo após a linha `external_sip_ip=$${local_ip}` (adição one-time durante deploy):
   ```xml
   <X-PRE-PROCESS cmd="include" data="/etc/freeswitch/vars-external-ip.xml"/>
   ```
   O último `set` prevalece — o include sobrescreve o `$${local_ip}`.
3. O sidecar chama `reloadxml` via ESL → FreeSWITCH re-processa o XML com o IP correto.
4. O sidecar chama `sofia profile upstream restart` via ESL → profile reinicia com `ext-sip-ip` correto.

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Include file `vars-external-ip.xml` + `reloadxml` + `sofia profile upstream restart` | Apenas upstream reinicia; sidecar possui o arquivo gerado; vars.xml inalterado após o include one-time | Requer volume mount do `conf/` no sidecar | ✅ |
| Reescrever `vars.xml` inteiro a cada mudança | Sem include adicional | Sidecar reescreve arquivo pré-existente do projeto; risco de corrupção | ❌ |
| `sofia restart` | Reinicia tudo de uma vez | Derruba interfones (viola RN-02) | ❌ |
| ESL `api global_setvar external_sip_ip=X` | Não requer escrita em disco | `reloadxml` posterior clobber o valor; `$${...}` no profile é compile-time | ❌ |

## Padrões aplicáveis

- **Sidecar pattern** (já implícito no stack: arq-uploader, arq-cleanup são containers auxiliares)
- **Polling pattern** para detecção de mudança de estado externo

## Fontes consultadas

- `_reversa_sdd/telephony/design.md` — topologia SIP, perfis internal/upstream
- `_reversa_sdd/infra/deployment/design.md` — docker-compose.app.yml, BunkerWeb
- `_reversa_sdd/gaps.md#GAP-UPSTREAM-01` — FAIL_WAIT dos gateways
- Documentação FreeSWITCH: `reloadxml`, `sofia profile restart`

## Histórico

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-29 | Versão inicial | reversa |
