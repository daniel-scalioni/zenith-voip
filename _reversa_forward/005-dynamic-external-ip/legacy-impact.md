# Legacy Impact: Detecção Dinâmica de IP Externo

> Feature: `005-dynamic-external-ip`
> Data: `2026-06-29`
> Âncora: `_reversa_sdd/architecture.md`, `_reversa_sdd/telephony/design.md`, `_reversa_sdd/domain.md`

## Arquivos Afetados

| Arquivo afetado | Componente (`_reversa_sdd/`) | Tipo | Severidade | Justificativa |
|-----------------|------------------------------|------|------------|---------------|
| `freeswitch/conf/vars.xml` | `architecture.md#FreeSWITCH` | regra-alterada | MEDIUM | Adição de diretiva include que sobrescreve `external_sip_ip`/`external_rtp_ip` em runtime — altera como o FreeSWITCH resolve o IP externo para anúncio SIP |
| `freeswitch/conf/vars-external-ip.xml` _(gerado)_ | `architecture.md#FreeSWITCH` | regra-nova | HIGH | Novo arquivo de configuração que controla o IP público anunciado nos headers SIP — crítico para o fluxo de registro upstream |
| `docker-compose.app.yml` | `infra/deployment/design.md` | componente-novo | LOW | Novo serviço `ip-watcher` adicionado ao stack; `network_mode: host` compartilha rede com FreeSWITCH |
| `sidecar/watcher.py` | `telephony/design.md#Interface ESL` | contrato-novo | MEDIUM | Novo consumidor do socket ESL — reutiliza o protocolo já documentado, mas adiciona comandos `reloadxml` e `sofia profile upstream restart` fora do fluxo normal |
| `sidecar/Dockerfile` | `infra/deployment/design.md` | componente-novo | LOW | Nova imagem Python 3.11-slim sem dependências além de `requests` |
| `.env.example` | — | regra-nova | LOW | Documenta novas variáveis de ambiente `EXTERNAL_IP_ENDPOINT`, `FREESWITCH_ESL_PASSWORD`, `POLL_INTERVAL`, `MOCK_EXTERNAL_IP` |

## Diff Conceitual por Componente

### FreeSWITCH (B2BUA)

**Antes:** `ext-sip-ip` e `ext-rtp-ip` do profile `upstream` resolviam sempre para `$${local_ip}` = `10.10.10.11` (IP privado). O FreeSWITCH anunciava este IP no `Contact` e SDP enviados ao VitalPBX, tornando os gateways inacessíveis remotamente (GAP-UPSTREAM-01).

**Depois:** `vars.xml` inclui `vars-external-ip.xml` após a linha original. O sidecar `ip-watcher` descobre o IP público via HTTP ou fallback `getsockname()`, grava o IP no arquivo include e dispara `reloadxml + sofia profile upstream restart`. O profile `internal` (interfones) não é afetado — recebe restart apenas o profile `upstream` (porta 5065), garantindo que REGISTERs dos ramais LAN permaneçam intactos.

### Interface ESL

**Antes:** O único consumidor ESL documentado era `src/telephony/esl_client.py` (FastAPI) — eventos assíncronos e comandos de controle de chamada.

**Depois:** Adiciona-se um segundo consumidor ESL (`ip-watcher`) que emite `api reloadxml` e `api sofia profile upstream restart` no ciclo de polling. O protocolo é o mesmo; o novo consumidor usa conexão TCP síncrona (socket raw) sem dependência da stack FastAPI.

### docker-compose.app.yml

**Antes:** 9 serviços (FreeSWITCH, fastapi-1, fastapi-2, arq-uploader, arq-cleanup, bunkerweb, ollama, piper-tts, postgres/redis via infra.yml).

**Depois:** 10 serviços. Novo `ip-watcher` com `network_mode: host` e volume mount `./freeswitch/conf:/etc/freeswitch`.

## Regras Preservadas

As seguintes regras 🟢 do `_reversa_sdd/domain.md` e `telephony/design.md` continuam intactas:

- **R07** — Porta SIP padrão `5060` (profile `internal`) não é alterada nem reiniciada
- Profile `upstream` opera em porta `5065` — separação mantida (nenhum profile consolidado)
- Autenticação ESL via `FREESWITCH_ESL_PASSWORD` — padrão de configuração via env var preservado
- `network_mode: host` do FreeSWITCH — não alterado
- Multitenancy e schema-per-tenant — nenhuma alteração no banco de dados

## Regras Modificadas

| Regra | Antes | Depois | Motivo |
|-------|-------|--------|--------|
| `ext-sip-ip` do profile `upstream` | Sempre `10.10.10.11` (IP privado, estático, via `$${local_ip}`) | IP público do CPD, atualizado dinamicamente via `vars-external-ip.xml` + `reloadxml` | GAP-UPSTREAM-01: gateways em FAIL_WAIT porque VitalPBX não alcança IP privado |
| `ext-rtp-ip` do profile `upstream` | Sempre `10.10.10.11` (via `$${local_ip}`) | IP público do CPD, sincronizado com `ext-sip-ip` | Consistência entre SIP Contact e SDP Media |

## Histórico

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-29 | Versão inicial gerada por `/reversa-coding` | reversa |
