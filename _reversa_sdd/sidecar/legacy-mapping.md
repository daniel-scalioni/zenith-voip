# Módulo: sidecar

> Gerado pelo Archaeologist — **2026-07-27** (módulo novo, delta D-11)
> Origem: feature `005-dynamic-external-ip`
> Confiança: 🟢 CONFIRMADO

Módulo que **não existia** na extração de 2026-06-19. Roda como container próprio
(`zenith-ip-watcher`), fora do processo FastAPI.

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `sidecar/watcher.py` | Watcher de IP externo → reconfigura FreeSWITCH | 160 |
| `sidecar/test_watcher.py` | Testes do watcher | 72 |
| `sidecar/Dockerfile` | Imagem do sidecar | 10 |
| `sidecar/requirements.txt` | Dependência única: `requests` | 1 |

## Problema que resolve

O host de deploy tem IP público **dinâmico**. O FreeSWITCH precisa anunciar o IP externo
correto em `external_sip_ip`/`external_rtp_ip` para que o VitalPBX upstream consiga entregar
SIP e RTP de volta. Um IP fixo no `vars.xml` quebra em toda troca de IP, e o registro
upstream cai silenciosamente.

## Fluxo de Controle

`main()` (`watcher.py:116`) — laço infinito com `POLL_INTERVAL` (default 60 s):

1. `get_external_ip(endpoint, mock_ip, verify_ssl)` (`:14`)
   - Se `MOCK_EXTERNAL_IP` estiver setado, retorna esse valor (modo teste).
   - Senão faz `GET` no `EXTERNAL_IP_ENDPOINT` (timeout 5 s).
   - **Fallback**: `socket.connect(("8.8.8.8", 53))` + `getsockname()` — funciona porque o
     sidecar roda em `network_mode: host`. Não envia pacote; só resolve a rota de saída.
   - Retorna `None` se as duas rotas falharem.
2. `get_current_ext_ip(...)` (`:79`) → `sofia status profile upstream` via ESL, procura a
   linha `Ext-SIP-IP` para descobrir o que o FreeSWITCH está anunciando **agora**.
3. Decisão:
   | Condição | Ação |
   |---|---|
   | `last_ip is None` (boot) | escreve + aplica → `acao_tomada: "startup"` |
   | `current_ip != freeswitch_ip` | escreve + aplica → `acao_tomada: "update"` |
   | iguais | nada → `acao_tomada: "none"` |
   | IP indescoberto | `acao_tomada: "error"` |
4. `write_vars_xml(ip, conf_path)` (`:37`) → grava
   `/etc/freeswitch/vars-external-ip.xml` com `external_sip_ip` e `external_rtp_ip`,
   usando **escrita atômica** (`.tmp` + `os.replace`) para o FreeSWITCH nunca ler um
   arquivo parcial.
5. `apply_update(...)` (`:93`) → `reloadxml` + `sofia profile upstream restart` via ESL.

## Protocolo ESL próprio

`_esl_send()` (`:51`) fala ESL em **socket TCP bruto e síncrono** (`socket` + `time.sleep`),
independente do `ESLClient` assíncrono de `src/telephony/`. Consome a saudação
`auth/request`, autentica, e envia comandos `api` lendo até encontrar `\n\n`.
🟡 Duplicação consciente: o sidecar não importa nada de `src/`, então não pode reusar o
`ESLClient` — o preço é ter dois dialetos de ESL no projeto.

## Observabilidade

Log estruturado em JSON puro (`logging` com `format="%(message)s"`), um objeto por ciclo:

```json
{"ts": "<iso8601 utc>", "ip_anterior": "1.2.3.4", "ip_atual": "5.6.7.8", "acao_tomada": "update"}
```

Eventos auxiliares: `http_fallback`, `getsockname_fallback`, `ip_discovery_failed`, `esl_error`.

## Configuração (variáveis de ambiente)

| Variável | Default | Descrição |
|---|---|---|
| `EXTERNAL_IP_ENDPOINT` | `""` | URL que retorna o IP público em texto puro |
| `MOCK_EXTERNAL_IP` | `""` | Curto-circuita a descoberta (testes) |
| `FREESWITCH_ESL_HOST` | `127.0.0.1` | ESL do FreeSWITCH (host network) |
| `FREESWITCH_ESL_PORT` | `8021` | — |
| `FREESWITCH_ESL_PASSWORD` | `ClueCon` | 🔴 default do FreeSWITCH (ver ADR-005) |
| `FREESWITCH_CONF_PATH` | `/etc/freeswitch` | Onde grava `vars-external-ip.xml` |
| `POLL_INTERVAL` | `60` | Segundos entre ciclos |
| `SSL_VERIFY` | `true` | Verificação TLS na consulta HTTP |

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| No boot sempre aplica, mesmo sem mudança de IP | `watcher.py:139-144` | 🟢 |
| Comparação é contra o IP que o FreeSWITCH anuncia, não contra o último visto | `watcher.py:145` | 🟢 |
| Escrita do `vars-external-ip.xml` é atômica | `watcher.py:45-48` | 🟢 |
| Fallback de descoberta por `getsockname()` quando o HTTP falha | `watcher.py:26-34` | 🟢 |
| Erro em um ciclo não derruba o watcher (loga e continua) | `watcher.py:153-154` | 🟢 |
| Aplicar mudança reinicia o profile `upstream` (derruba registros ativos) | `watcher.py:95` | 🟡 |

## Interação com o GAP-NET-01

`vars.xml` define `external_sip_ip`/`external_rtp_ip` como `$${local_ip}` e **depois**
inclui `vars-external-ip.xml`, que o sidecar sobrescreve com o IP público.

✅ **Verificado em 2026-07-27:** isso **não** reintroduz o GAP-NET-01. Os profiles
`internal.xml`, `internal-7060.xml` e `internal-5062.xml` usam `$${local_ip}` **literal**
(linhas 18-19), não a variável — o fix do GAP-NET-01 desacoplou os profiles internos da
variável de IP externo. O único consumidor de `external_*_ip` é `upstream.xml`, que fala com
o VitalPBX pela internet e deve mesmo anunciar IP público.

⚠️ Invariante: se algum profile `internal*` voltar a usar `$${external_*_ip}`, o conflito
reaparece.

## Riscos

| Risco | Nota |
|---|---|
| `sofia profile upstream restart` a cada troca de IP | Derruba ~939 gateways e os re-registra; chamadas em curso no profile caem |
| Sem backoff | Falha persistente de rede gera um ciclo de erro a cada 60 s indefinidamente |
| `verify=False` possível via `SSL_VERIFY=false` | Descoberta de IP sujeita a MITM se desligado |
