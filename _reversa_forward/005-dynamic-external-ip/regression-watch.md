# Regression Watch: Detecção Dinâmica de IP Externo

> Feature: `005-dynamic-external-ip`
> Gerado em: `2026-06-29`
> Âncora legado: `_reversa_sdd/telephony/design.md`, `_reversa_sdd/architecture.md`

## Watch Items

| ID | Origem | Regra esperada após a mudança | Tipo de verificação | Sinal de violação |
|----|--------|-------------------------------|---------------------|-------------------|
| W001 | `_reversa_sdd/telephony/design.md#Perfis SIP` | Profile `internal` (porta 5060) permanece `RUNNING` durante e após `sofia profile upstream restart` | presença | `sofia status profile internal` exibe `UNLOADED` ou `FAILED` |
| W002 | `_reversa_sdd/telephony/design.md#Perfis SIP` | Ramais registrados no profile `internal` mantêm seus registros durante o ciclo de atualização de IP | presença | `sofia status profile internal` mostra contagem de registros = 0 enquanto `ip-watcher` executa update |
| W003 | `_reversa_sdd/gaps.md#GAP-UPSTREAM-01` | Após ciclo de startup do `ip-watcher`, gateways upstream saem de `FAIL_WAIT` e atingem `REGED` | presença | `sofia status gateway upstream-*` exibe `FAIL_WAIT` persistente após 90s do startup |
| W004 | `freeswitch/conf/vars.xml` | Arquivo `vars-external-ip.xml` é criado em `/etc/freeswitch/` com IP público real (não `10.10.10.11`) | redação | Conteúdo do arquivo exibe `10.10.10.11` ou IP privado RFC1918 após startup do sidecar |
| W005 | `_reversa_sdd/gaps.md` (política de credenciais) | Nenhuma credencial ESL (senha), token ou dado sensível aparece nos logs do `ip-watcher` | ausência | `docker logs zenith-ip-watcher` contém a string da senha ESL ou qualquer credencial |
| W006 | `_reversa_sdd/architecture.md#Papel do FreeSWITCH` | Container `ip-watcher` reinicia automaticamente após crash sem afetar os outros serviços do compose | presença | Crash do `ip-watcher` causa indisponibilidade de `freeswitch`, `fastapi-1` ou `fastapi-2` |

## Observações (🟡/🔴 — sem peso de regressão)

- **RN-03 timing:** Detecção pode levar até um ciclo completo de polling (60s) + tempo de reload. Em cenário de failover crítico, o downtime observável pode superar 60s. Monitorar em campo se isso impacta o SLA.
- **Fallback `getsockname()`:** Se o endpoint HTTP ficar indisponível, o sidecar usa o IP de saída via UDP socket. Em NAT em cascata (CPD atrás de outro NAT), este IP pode não ser o IP público final. Confirmar topologia de rede em produção.

## Histórico de re-extrações

### Re-extração 2026-07-08 22:31

| ID | Veredito | Observação |
|----|----------|------------|
| W001 | 🟢 verde | `internal` (5060) permanece `RUNNING` — confirmado ao vivo durante deploy da feature 006 (dois profiles novos criados/iniciados sem interrupção do `internal`) |
| W002 | 🟢 verde | Regra preservada em `telephony/design.md#3` — profiles de entrada continuam isolados do `upstream` |
| W003 | 🟢 verde | `gaps.md#GAP-UPSTREAM-01` atualizado para ✅ Resolvida — `upstream-1001` confirmado `REGED`/`UP` nesta sessão |
| W004 | 🟡 amarelo | Não re-verificado diretamente nesta sessão (foco foi na feature 006); sem evidência de regressão |
| W005 | 🟡 amarelo | Não re-verificado diretamente nesta sessão; sem evidência de regressão |
| W006 | 🟡 amarelo | Não re-verificado diretamente nesta sessão; sem evidência de regressão |

<!-- Preenchido automaticamente pelo /reversa quando a pipeline reversa for re-executada. -->

## Arquivadas

<!-- Items descontinuados por mudança de requisito ou remoção de feature. -->
