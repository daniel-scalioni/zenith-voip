# Actions: Detecção Dinâmica de IP Externo no FreeSWITCH

> Identificador: `005-dynamic-external-ip`
> Data: `2026-06-29`
> Roadmap: `_reversa_forward/005-dynamic-external-ip/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 12 |
| Paralelizáveis (`[//]`) | 7 |
| Maior cadeia de dependência | 5 (T001 → T005 → T006 → T007 → T008) |

## Fase 1, Preparação

<!-- Setup, scaffolding, configuração inicial dos artefatos de infraestrutura. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar `sidecar/Dockerfile` (FROM python:3.11-slim, instala `requests`, define entrypoint `watcher.py`) e `sidecar/requirements.txt` (`requests>=2.31`) sem lógica de negócio — apenas scaffolding compilável | - | `[//]` | `sidecar/Dockerfile`, `sidecar/requirements.txt` | 🟢 | `[X]` |
| T002 | Editar `freeswitch/conf/vars.xml`: adicionar `<X-PRE-PROCESS cmd="include" data="/etc/freeswitch/vars-external-ip.xml"/>` imediatamente após a linha `external_sip_ip=$${local_ip}` (one-time; o arquivo nunca mais é tocado) | - | `[//]` | `freeswitch/conf/vars.xml` | 🟢 | `[X]` |
| T003 | Adicionar serviço `ip-watcher` em `docker-compose.app.yml` com `build: ./sidecar`, `network_mode: host`, volume `./freeswitch/conf:/etc/freeswitch` e env vars placeholder (`EXTERNAL_IP_ENDPOINT`, `FREESWITCH_ESL_PASSWORD`, `MOCK_EXTERNAL_IP`, `POLL_INTERVAL`) — sem `env_file` por ora | - | `[//]` | `docker-compose.app.yml` | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Testes unitários do sidecar; podem ser escritos logo após o scaffolding (T001), antes da implementação do núcleo. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T004 | Criar `sidecar/test_watcher.py` com três grupos de testes: (1) `get_external_ip` com HTTP mock retornando IP e com `requests.exceptions.RequestException`; (2) fallback `getsockname()` retornando IP correto; (3) `write_vars_xml` verifica que o arquivo XML gerado contém as duas diretivas `set` com o IP esperado | T001 | `[//]` | `sidecar/test_watcher.py` | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Lógica central do sidecar em sequência estrita (todas as funções vivem em watcher.py). -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T005 | Implementar `get_external_ip(endpoint: str, mock_ip: str \| None) -> str \| None` em `sidecar/watcher.py`: se `mock_ip` estiver setado retorna direto; senão faz HTTP GET com timeout=5s no `endpoint`; em falha HTTP abre socket UDP (`socket.SOCK_DGRAM`) para `8.8.8.8:53`, chama `getsockname()` e retorna o IP local — fonte: D-02, D-04 | T001 | - | `sidecar/watcher.py` | 🟢 | `[X]` |
| T006 | Adicionar a `sidecar/watcher.py`: (a) `write_vars_xml(ip: str, conf_path: str)` que grava `{conf_path}/vars-external-ip.xml` com as duas diretivas `<X-PRE-PROCESS cmd="set" data="external_sip_ip=IP"/>` e `external_rtp_ip=IP`; (b) `get_current_ext_ip(host, port, password) -> str \| None` que abre socket TCP para ESL, autentica, envia `api sofia status profile upstream` e parseia o campo `Ext-SIP-IP:` da resposta — fonte: D-05 | T005 | - | `sidecar/watcher.py` | 🟢 | `[X]` |
| T007 | Adicionar a `sidecar/watcher.py`: (a) `apply_update(host, port, password)` que abre conexão ESL, envia `api reloadxml`, valida resposta `+OK`, envia `api sofia profile upstream restart`, valida resposta; (b) `main()` que lê env vars, inicia loop de polling com `POLL_INTERVAL` (default 60s), chama `get_external_ip` → compara com `get_current_ext_ip` → se diferente: `write_vars_xml` + `apply_update` → log estruturado; captura exceções sem crashar | T006 | - | `sidecar/watcher.py` | 🟢 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Completar a entrada `ip-watcher` em `docker-compose.app.yml`: adicionar `env_file: .env`, mapear `environment` com os defaults corretos (`FREESWITCH_ESL_HOST=127.0.0.1`, `FREESWITCH_ESL_PORT=8021`, `POLL_INTERVAL=60`), adicionar `restart: unless-stopped` e `depends_on: freeswitch` | T003, T007 | - | `docker-compose.app.yml` | 🟢 | `[X]` |
| T009 | Criar `.env.example` na raiz do projeto com as entradas das vars do sidecar: `EXTERNAL_IP_ENDPOINT=`, `FREESWITCH_ESL_PASSWORD=ClueCon`, `MOCK_EXTERNAL_IP=` (comentado), `POLL_INTERVAL=60` — se `.env.example` já existir, apenas adicionar o bloco `# ip-watcher` ao final | - | `[//]` | `.env.example` | 🟢 | `[X]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T010 | Refinar logging em `sidecar/watcher.py`: garantir que cada ciclo emite uma linha JSON com campos `timestamp` (ISO-8601), `ip_anterior`, `ip_atual`, `acao_tomada` (`none`/`update`/`startup`/`error`); emitir `WARNING` quando fallback `getsockname()` for usado; emitir `ERROR` quando `get_external_ip` retornar `None`; sem nenhum campo de credencial nos logs | T007 | - | `sidecar/watcher.py` | 🟡 | `[X]` |
| T011 | Corrigir linha do critério de pronto §10 do `roadmap.md`: substituir `- [ ] BunkerWeb DNAT UDP 5065 → FreeSWITCH funcional` por `- [ ] DNAT UDP 5065 → 10.10.10.11:5065 configurado no roteador/iptables do CPD e validado` | - | `[//]` | `_reversa_forward/005-dynamic-external-ip/roadmap.md` | 🟢 | `[X]` |
| T012 | Criar `_reversa_forward/005-dynamic-external-ip/regression-watch.md` listando os pontos de regressão: (1) profile `internal` permanece up após `sofia profile upstream restart`; (2) gateways upstream voltam a REGED após ciclo; (3) `vars-external-ip.xml` não vaza credenciais ESL; (4) container `ip-watcher` reinicia sozinho após crash sem afetar outros serviços | - | `[//]` | `_reversa_forward/005-dynamic-external-ip/regression-watch.md` | 🟢 | `[X]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-29 | Versão inicial gerada por `/reversa-to-do` | reversa |
