# Roadmap: Detecção Dinâmica de IP Externo no FreeSWITCH

> Identificador: `005-dynamic-external-ip`
> Data: `2026-06-29`
> Requirements: `_reversa_forward/005-dynamic-external-ip/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Adicionar um container sidecar (Alpine/Python) ao `docker-compose.app.yml` que consulta periodicamente um endpoint HTTP configurável para descobrir o IP público do CPD. O sidecar conecta-se ao FreeSWITCH via socket ESL (`172.20.0.1:8021`, pois o FreeSWITCH usa `network_mode: host`), compara o IP obtido com o valor atual de `ext-sip-ip`/`ext-rtp-ip` no profile `upstream` e, se houver mudança:

1. Grava o novo IP em `conf/vars-external-ip.xml` (arquivo dedicado que o sidecar possui e que o `vars.xml` inclui logo após a linha `external_sip_ip=$${local_ip}` — o último `set` prevalece no X-PRE-PROCESS).
2. Executa `reloadxml` via ESL (re-processa o XML e lê o novo IP do arquivo include).
3. Executa `sofia profile upstream restart` via ESL (relê o profile já com o novo `ext-sip-ip` baked in).

O profile `internal` (interfones) não é tocado. A porta UDP 5065 é roteada ao host por regra de DNAT no roteador/iptables do CPD (não BunkerWeb — ver §9).

## 2. Princípios aplicados

Nenhum princípio registrado em `.reversa/principles.md`. N/A.

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|---------------|--------------------------|-------------|
| D-01 | Container sidecar Alpine/Python para monitoramento de IP | Isolamento total do container FreeSWITCH (RF-06); sem build customizado; sem modificar entrypoint; sem depender de cron no host | (a) Script no entrypoint do FreeSWITCH → viola RF-06, exige Dockerfile próprio; (b) Cron no host Docker → dependência externa ao Docker Compose, quebra portabilidade | 🟢 |
| D-02 | Descoberta de IP via HTTP (endpoint configurável via env var) em vez de STUN | STUN desativado no ambiente do cliente. HTTP é mais simples, não requer UDP 3478 aberto, endpoint é DNS próprio do CPD | STUN → não usado no cliente; ifconfig.me → depende de serviço externo | 🟢 |
| D-03 | Polling a cada 60s | Atende RN-03 (≤60s) sem overhead excessivo | 30s → mais overhead; 45s → meio-termo sem ganho claro | 🟢 |
| D-04 | Fallback: source IP do próprio sidecar via `getsockname()` | Como o sidecar usa `network_mode: host`, seu IP de saída é o mesmo do FreeSWITCH. Em caso de falha do endpoint HTTP, o sidecar abre um socket UDP para um destino remoto (ex.: `8.8.8.8:53`) e consulta `getsockname()` — o endereço local retornado é o IP público de saída do CPD. | Segundo endpoint HTTP → mais dependência externa; manter último IP → mascara falha | 🟢 |
| D-05 | Ações `reloadxml` + `sofia profile upstream restart` | `sofia profile upstream restart` reinicia APENAS o upstream, sem afetar o internal (interfones). `reloadxml` reavalia `$${external_sip_ip}` | `sofia restart` → derruba todos os profiles, viola RN-02 | 🟢 |
| D-06 | Port forwarding via BunkerWeb (DNAT) | BunkerWeb já é o proxy reverso, não requer nova ferramenta | Port forwarding no roteador físico → menos flexível | 🟢 |

## 4. Premissas

Nenhuma dúvida pendente no requirements. Sem premissas.

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|-----------------------------|-----------------|--------|
| FreeSWITCH `vars.xml` | `freeswitch/conf/vars.xml` | config-alterada | Adicionar uma diretiva `X-PRE-PROCESS include` apontando para `vars-external-ip.xml` logo após a linha `external_sip_ip=$${local_ip}` (one-time; o arquivo em si nunca é reescrito depois) |
| `vars-external-ip.xml` | — | arquivo-novo | Criado pelo sidecar; contém as diretivas `set` para `external_sip_ip` e `external_rtp_ip` com o IP público real; sobrescreve o `$${local_ip}` definido antes no `vars.xml` |
| ESL Client | `_reversa_sdd/telephony/design.md#Interface ESL` | contrato-novo | Sidecar conecta via ESL (`172.20.0.1:8021`) e usa `send_api` para `reloadxml` e `sofia profile upstream restart` |
| docker-compose.app.yml | `_reversa_sdd/infra/deployment/design.md` | componente-novo | Novo serviço `ip-watcher` (sidecar) com `network_mode: host` e volume mount `./freeswitch/conf:/etc/freeswitch` |

## 6. Delta no modelo de dados

- Nenhuma mudança no modelo de dados PostgreSQL.
- Nenhuma migration Alembic.
- Detalhe completo em: `_reversa_forward/005-dynamic-external-ip/data-delta.md`

## 7. Delta de contratos externos

Nenhum contrato externo novo ou alterado. O sidecar consome:
- HTTP (endpoint configurável via env var) — descoberta de IP
- ESL (socket local) — comandos no FreeSWITCH

Ambos internos ao ambiente Docker.

## 8. Plano de migração

1. Criar diretório `sidecar/` com `Dockerfile`, `requirements.txt`, `watcher.py`
   - `watcher.py` deve: (a) descobrir IP via HTTP endpoint ou fallback `getsockname()`; (b) gravar `vars-external-ip.xml` em `/etc/freeswitch/`; (c) conectar via ESL e executar `reloadxml` + `sofia profile upstream restart`; (d) polling loop de 60s
2. Adicionar em `freeswitch/conf/vars.xml`, após a linha `external_sip_ip=$${local_ip}`, a diretiva:
   ```xml
   <X-PRE-PROCESS cmd="include" data="/etc/freeswitch/vars-external-ip.xml"/>
   ```
   (Edição one-time; o `vars.xml` não é tocado novamente após isso)
3. Adicionar serviço `ip-watcher` no `docker-compose.app.yml`:
   - `network_mode: host` (acesso a ESL em `127.0.0.1:8021` e IP de saída correto para fallback)
   - Volume: `./freeswitch/conf:/etc/freeswitch` (para escrever `vars-external-ip.xml`)
4. Configurar env vars no `.env`: `EXTERNAL_IP_ENDPOINT`, `MOCK_EXTERNAL_IP` (dev), `FREESWITCH_ESL_PASSWORD`
5. Verificar/configurar DNAT UDP 5065 → 10.10.10.11:5065 no roteador do CPD ou via iptables no host (não BunkerWeb)
6. Subir stack: `docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d ip-watcher`
7. Validar: `sofia status profile upstream` exibe IP público em Ext-SIP-IP
8. Validar: gateways upstream saem de FAIL_WAIT → REGED

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| ESL password padrão (`ClueCon`) em produção | alto | baixa | Usar senha configurada via env var (já existe em `config.py`) |
| `reloadxml` falha silenciosamente | médio | baixa | Sidecar valida saída do ESL; log `ip_anterior`, `ip_atual`, `acao_tomada` |
| Endpoint HTTP retorna IP incorreto | alto | baixa | Fallback source IP; log warning se IP suspeito |
| DNAT UDP 5065 + failover ISP | alto | média | DNAT é responsabilidade do roteador do CPD ou de regras `iptables` no host (FreeSWITCH usa `network_mode: host` — a porta 5065 já está bound no host). BunkerWeb não processa UDP e não deve ser configurado para isso. |
| Múltiplos sidecars concorrentes | baixo | baixa | Apenas 1 instância necessária; comando idempotente |

## 10. Critério de pronto

- [X] Sidecar em execução, logs mostram verificação a cada 60s
- [X] `sofia status profile upstream` exibe IP público (não `10.10.10.11`) em Ext-SIP-IP — validado: `200.170.149.139`
- [ ] Gateway upstream sai de FAIL_WAIT e atinge REGED — pendente: IP `200.170.149.139` liberado no VitalPBX em 2026-06-30, aguardando confirmação
- [ ] Profile internal permanece ativo após ciclo de atualização
- [X] `MOCK_EXTERNAL_IP` funciona em dev sem endpoint real
- [X] DNAT UDP 5065 → 10.10.10.11:5065 configurado no roteador/iptables do CPD e validado
- [X] Todas as ações do `actions.md` marcadas `[X]`
- [X] `regression-watch.md` gerado

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-29 | Versão inicial gerada por `/reversa-plan` | reversa |
| 2026-06-30 | Deploy validado em produção: sidecar operacional, `Ext-SIP-IP=200.170.149.139`, IP liberado no firewall do VitalPBX | daniel |
