---
spec:
  component: ip-watcher
  layer: sidecar
  status: active
  version: 1.0.0
  language: python
  patterns: []
  inputs:
    - {name: external_ip, type: str, from: EXTERNAL_IP_ENDPOINT (HTTP) ou rota de saída}
    - {name: current_ext_sip_ip, type: str, from: freeswitch (ESL sofia status)}
  outputs:
    - {name: vars-external-ip.xml, type: file, to: freeswitch/conf}
    - {name: reload_command, type: esl_api, to: freeswitch}
  dependencies: []
  events_produced: []
  updated_at: 2026-07-27
---

# Sidecar — IP Watcher

> Gerado pelo Writer — **2026-07-27** (componente novo, feature `005-dynamic-external-ip`)

## Visão Geral

Container independente (`zenith-ip-watcher`) que mantém o IP externo anunciado pelo FreeSWITCH
sincronizado com o IP público real do host. Roda em `network_mode: host`, compartilha o volume
de configuração do FreeSWITCH e fala ESL diretamente.

**Não importa nada de `src/`** — é um processo isolado, com dependência única (`requests`).

## Problema

O host de deploy tem IP público dinâmico. O FreeSWITCH precisa anunciar o IP externo correto
em `external_sip_ip`/`external_rtp_ip` para que o VitalPBX upstream entregue SIP e RTP de
volta. Um IP fixo no `vars.xml` quebra em toda troca de IP, e o registro upstream cai sem
sinal claro.

## Responsabilidades

- Descobrir o IP público do host, com rota primária HTTP e fallback local
- Consultar o IP que o FreeSWITCH está anunciando **agora** (não confiar no último visto)
- Escrever `vars-external-ip.xml` de forma atômica quando houver divergência
- Aplicar a mudança (`reloadxml` + `sofia profile upstream restart`)
- Emitir um registro JSON estruturado por ciclo

## Requisitos Funcionais

| ID | Requisito | Prioridade | Status |
|----|-----------|-----------|--------|
| RF-01 | Descobrir o IP externo via `EXTERNAL_IP_ENDPOINT` (HTTP, timeout 5s) | Must | ✅ |
| RF-02 | Ter fallback de descoberta por rota de saída (`getsockname`) quando o HTTP falha | Must | ✅ |
| RF-03 | Permitir `MOCK_EXTERNAL_IP` para testes, curto-circuitando a descoberta | Should | ✅ |
| RF-04 | Ler o `Ext-SIP-IP` corrente do profile `upstream` via ESL | Must | ✅ |
| RF-05 | Escrever `vars-external-ip.xml` atomicamente (`.tmp` + `os.replace`) | Must | ✅ |
| RF-06 | Aplicar sempre no primeiro ciclo (boot), mesmo sem divergência | Must | ✅ |
| RF-07 | Aplicar quando o IP descoberto divergir do anunciado | Must | ✅ |
| RF-08 | Emitir log JSON com `ts`, `ip_anterior`, `ip_atual`, `acao_tomada` | Must | ✅ |
| RF-09 | Continuar operando após erro em um ciclo | Must | ✅ |

## Requisitos Não-Funcionais

| ID | Requisito | Status |
|----|-----------|--------|
| RNF-01 | O FreeSWITCH nunca deve ler um arquivo de config parcial | ✅ escrita atômica |
| RNF-02 | Um ciclo com falha não pode encerrar o processo | ✅ `except Exception` amplo com log |
| RNF-03 | A descoberta de IP deve resistir a indisponibilidade do endpoint HTTP | ✅ fallback local |
| RNF-04 | Backoff em falha persistente | 🔴 **não atendido** — intervalo fixo, um erro a cada 60 s indefinidamente |
| RNF-05 | Verificação TLS na consulta de IP | 🟡 configurável via `SSL_VERIFY`; desligá-la expõe a descoberta a MITM |

## Valores de `acao_tomada`

| Valor | Quando |
|---|---|
| `startup` | Primeiro ciclo após o boot |
| `update` | IP descoberto difere do anunciado pelo FreeSWITCH |
| `none` | IPs coincidem, nada a fazer |
| `error` | IP não pôde ser descoberto, ou exceção no ciclo |

## Restrições

- Exige `network_mode: host` — o fallback `getsockname` depende de ver a rota real do host
- Exige o volume `./freeswitch/conf` montado em escrita
- `vars.xml` **precisa** incluir `vars-external-ip.xml` **depois** dos defaults, senão a
  sobrescrita não tem efeito

## Rastreabilidade

| Arquivo | Função | Cobertura |
|---------|--------|-----------|
| `sidecar/watcher.py` | `get_external_ip()` | 🟢 `sidecar/test_watcher.py` |
| `sidecar/watcher.py` | `write_vars_xml()` | 🟢 |
| `sidecar/watcher.py` | `get_current_ext_ip()` | 🟢 |
| `sidecar/watcher.py` | `apply_update()` | 🟢 |
| `sidecar/watcher.py` | `main()` | 🟡 laço infinito, sem teste direto |

## Lacunas

| ID | Descrição |
|---|---|
| ~~GAP-RE-06~~ | ✅ Fechada em 2026-07-27 — os profiles `internal*` usam `$${local_ip}` literal, não a variável que o watcher escreve; só o `upstream` é afetado, e corretamente. Decisão do usuário: watcher roda no deploy atual |
| — | `sofia profile upstream restart` derruba ~939 gateways a cada troca de IP; chamadas em curso no profile caem |
| — | Sem backoff em falha persistente (RNF-04) |
