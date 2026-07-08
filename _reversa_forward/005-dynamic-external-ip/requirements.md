# Requirements: Detecção Dinâmica de IP Externo no FreeSWITCH

> Identificador: `005-dynamic-external-ip`
> Data: `2026-06-29`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

O CPD do cliente opera com múltiplos provedores de internet em failover ativo, o que faz o IP público rotacionar sem aviso. O FreeSWITCH atualmente anuncia o IP privado `10.10.10.11` nos headers `Contact` e SDP enviados ao VitalPBX (nuvem), impedindo que o VitalPBX roteie chamadas de volta. Esta feature corrige o anúncio de IP externo em dois momentos: (1) na inicialização, usando HTTP (endpoint configurável via variável de ambiente) para descobrir o IP público correto; (2) em runtime, usando um processo de monitoramento que detecta troca de provedor e atualiza o FreeSWITCH automaticamente sem reinício completo nem intervenção manual.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/infra/deployment/design.md#B2BUA Registration Forwarding` | Profile `upstream` usa `ext-sip-ip=$${external_sip_ip}` que resolve para `$${local_ip}` = 10.10.10.11 (IP privado RFC1918) | 🟢 |
| `_reversa_sdd/telephony/design.md#Perfis SIP do FreeSWITCH` | Profile `upstream` (porta 5065) é separado do `internal` (porta 5060) — rescan do `upstream` não afeta REGISTERs dos interfones | 🟢 |
| `_reversa_sdd/gaps.md#GAP-UPSTREAM-01` | Gateways em FAIL_WAIT pós-deploy; causa: VitalPBX na nuvem não consegue responder para IP privado nos headers SIP | 🟢 |
| `_reversa_sdd/architecture.md#Papel do FreeSWITCH` | FreeSWITCH é B2BUA com Registration Forwarding — VitalPBX precisa enviar INVITEs de volta ao FreeSWITCH para chamadas inbound | 🟢 |
| `freeswitch/conf/vars.xml` | `external_sip_ip` e `external_rtp_ip` apontam para `$${local_ip}` — IP privado na nuvem é inacessível | 🟢 |
| `freeswitch/conf/sip_profiles/upstream.xml` | `ext-sip-ip` e `ext-rtp-ip` usam `$${...}` (compile-time) — só atualizam com `reloadxml` | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Operador de infraestrutura (CPD) | Fazer failover de ISP sem intervir no FreeSWITCH | Link primário cai às 03h; roteador muda para ISP secundário; FreeSWITCH detecta novo IP em ≤ 60s e re-registra gateways upstream automaticamente |
| Desenvolvedor Zenith | Configurar o sistema uma vez e esquecer | Nenhuma tarefa manual recorrente de atualização de IP — o sistema é autossuficiente |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** O FreeSWITCH DEVE anunciar o IP público do CPD (não o IP privado) nos headers `Contact`, `Via` e `SDP` enviados ao VitalPBX. 🟢
   - Origem no legado: `_reversa_sdd/telephony/design.md#Topologia SIP`
   - Tipo: nova

2. **RN-02:** A atualização de IP externo NÃO pode reiniciar o profile `internal` (porta 5060) — interfones em uso não podem ser desconectados. 🟢
   - Origem no legado: `_reversa_sdd/telephony/design.md#Perfis SIP`
   - Tipo: nova

3. **RN-03:** A re-detecção de IP deve acontecer dentro de um ciclo de polling (60s) após a troca de provedor, sem intervenção manual. O gateway retorna ao estado REGED em ≤ 90s após a detecção (tempo de reload + re-registro). 🟡
   - Tipo: nova

4. **RN-04:** O mecanismo de detecção não pode armazenar nem logar credenciais SIP ou senhas de ramal. 🟢
   - Origem no legado: `_reversa_sdd/gaps.md` (política de não committar credenciais)
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Na inicialização, `external_sip_ip` e `external_rtp_ip` devem ser descobertos via HTTP (endpoint configurável via variável de ambiente) e refletir o IP público atual | Must | `sofia status profile upstream` exibe IP público do CPD (não 10.10.10.11) no campo `Ext-SIP-IP` | 🟢 |
| RF-02 | Um processo de monitoramento deve verificar periodicamente (a cada 60s) o IP público e compará-lo ao valor atual do FreeSWITCH | Must | Processo em execução contínua; log de verificação periódica visível a cada 60s | 🟢 |
| RF-03 | Ao detectar mudança de IP, o monitoramento deve executar `reloadxml` seguido de `sofia profile upstream restart` no FreeSWITCH | Must | Após troca de ISP simulada, gateway `upstream-1001` volta ao estado `REGED` em ≤ 90s | 🟡 |
| RF-04 | O profile `internal` (interfones) NÃO deve ser reiniciado durante a atualização de IP | Must | Ramal registrado no `internal` permanece registrado durante o ciclo de atualização | 🟢 |
| RF-05 | O IP público deve ser obtido via endpoint HTTP configurável via variável de ambiente. STUN removido como opção (não usado no ambiente do cliente). | Should | `EXTERNAL_IP_ENDPOINT` definida via env var | 🟢 |
| RF-06 | O mecanismo deve ser compatível com a imagem `safarov/freeswitch:1.10.12` sem exigir build customizado do container FreeSWITCH | Should | Funciona sem alterar o `Dockerfile` do FreeSWITCH | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Disponibilidade | Atualização de IP não causa downtime no profile `internal` | Profile `upstream` é isolado do `internal` — design confirmado em `_reversa_sdd/telephony/design.md` | 🟢 |
| Latência | IP change detection em ≤ 60 segundos após failover de ISP | Requisito de negócio: chamadas ativas não devem falhar por mais de 1 minuto por troca de provedor | 🟡 |
| Segurança | Nenhuma credencial SIP, senha de ramal ou secret de ENV exposta no mecanismo de detecção | Política de segurança do projeto: credenciais nunca em scripts versionados | 🟢 |
| Observabilidade | Log estruturado a cada verificação de IP: `ip_anterior`, `ip_atual`, `acao_tomada` | Facilitação de diagnóstico de falhas de registro upstream | 🟡 |
| Compatibilidade | Deve funcionar com `docker-compose.app.yml` existente, sem quebrar outros serviços | Restrição de escopo: não redesenhar infra para esta feature | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Inicialização com IP público correto
  Dado que o CPD tem IP público X.X.X.X
  Quando o container FreeSWITCH inicializa
  Então fs_cli -x "sofia status profile upstream" exibe X.X.X.X no campo Ext-SIP-IP
  E fs_cli -x "sofia status profile upstream" NÃO exibe 10.10.10.11 no campo Ext-SIP-IP

Cenário: Failover de ISP detectado e corrigido automaticamente
  Dado que o FreeSWITCH está rodando com IP público X.X.X.X
  E o gateway upstream-1001 está no estado REGED
  Quando o ISP muda e o IP público passa a ser Y.Y.Y.Y
  Então em até 60 segundos o processo de monitoramento detecta a mudança
  E executa reloadxml e sofia profile upstream restart
  E em até 90 segundos o gateway upstream-1001 volta ao estado REGED com novo IP
  E o profile internal (porta 5060) permanece ativo durante todo o processo

Cenário: Profile internal não é afetado
  Dado que o ramal 1001 está registrado no FreeSWITCH (profile internal)
  Quando o mecanismo de atualização de IP executa
  Então fs_cli -x "sofia status profile internal" não muda de estado
  E o registro do ramal 1001 no internal permanece válido

Cenário: IP público indisponível (ambos os ISPs caem)
  Dado que o CPD perde conectividade com a internet
  Quando o processo de monitoramento verifica o IP
  Então o processo loga o erro sem travar
  E continua tentando a cada ciclo (sem crashar o container)
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 — STUN na inicialização | Must | Sem IP público correto no startup, nenhum gateway registra no VitalPBX |
| RF-03 — reloadxml + upstream restart | Must | Mecanismo de atualização em runtime sem restart completo |
| RF-04 — internal não reinicia | Must | Não pode desconectar interfones em uso |
| RF-02 — monitoramento periódico | Must | Núcleo da feature; sem monitoramento não há detecção automática |
| RF-05 — método de detecção configurável | Should | HTTP como padrão é suficiente para o MVP; poder trocar de endpoint é bônus |
| RF-06 — sem build customizado | Should | Evita dependência do token SignalWire (GAP-11); sidecar container atende |

## 9. Esclarecimentos

### Sessão 2026-06-29

- **Q:** Port forwarding obrigatório? Apenas UDP 5065 ou também 5060?
  **R:** UDP 5065 (profile upstream) precisa chegar ao host `10.10.10.11`. Como o FreeSWITCH usa `network_mode: host`, já está bound na interface do host — o forwarding é configurado no roteador do CPD ou via `iptables` no host, **não pelo BunkerWeb** (que é HTTP/HTTPS only). Porta 5060 (internal) não precisa ser exposta — interfones estão na LAN.

- **Q:** Qual abordagem de implementação do watcher?
  **R:** Container sidecar Alpine/Python com acesso ao socket ESL. Descoberta de IP via HTTP (endpoint configurável via env var). Polling a cada 60s. STUN desativado (não usado no ambiente do cliente). Fallback em falha: logar erro e repetir no próximo ciclo. Testabilidade via env var `MOCK_EXTERNAL_IP` em dev.

- **Q:** O problema é detectar IP público ou forçar o FreeSWITCH a anunciar o IP correto?
  **R:** O IP público já é conhecido (visível nos registros dos ramais: `189.112.222.244`). O problema é que o FreeSWITCH anuncia `10.10.10.11` no Contact/SDP do REGISTER upstream. A correção é garantir que `ext-sip-ip` e `ext-rtp-ip` sejam atualizados dinamicamente quando o IP de saída mudar (failover de ISP).

- **Q:** Qual intervalo de polling do watcher?
  **R:** 60 segundos.

- **Q:** E se o endpoint HTTP ficar indisponível?
  **R:** O endpoint pode ser um registro DNS próprio do cliente (ex: resolvendo um FQDN que retorna o IP público atual do CPD). Se ele falhar, usar o IP de saída do próprio FreeSWITCH (source IP do socket de conexão), pois o roteamento garante que a saída é o IP correto a ser anunciado.

## 10. Lacunas

- 🟢 **Port forwarding:** UDP 5065 (profile upstream) é exposto via roteador do CPD ou `iptables` no host — não via BunkerWeb (HTTP only). Porta 5060 não precisa de exposição externa.

- 🟢 **Implementação do watcher:** Sidecar Alpine/Python com ESL socket. Detecção via HTTP (endpoint configurável via env var). Polling a 60s. Mock via `MOCK_EXTERNAL_IP`.

- 🟢 **Fallback HTTP:** Se o endpoint configurado falhar, usar o IP de saída (source IP do socket) do próprio FreeSWITCH como fallback.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-29 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-06-29 | Esclarecimentos da sessão 2026-06-29 integrados: port forwarding (BunkerWeb), sidecar confirmado, HTTP como método primário, STUN removido, polling 60s, mock via env var, fallback source IP | reversa-clarify |
