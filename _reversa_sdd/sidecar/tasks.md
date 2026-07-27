---
spec:
  component: ip-watcher
  layer: sidecar
  status: active
  version: 1.0.0
  updated_at: 2026-07-27
---

# Sidecar — IP Watcher · Tasks

> Gerado pelo Writer — **2026-07-27** (componente novo)

## Estado atual

| # | Tarefa | Status |
|---|--------|--------|
| T-01 | Descoberta de IP externo via HTTP com timeout | ✅ implementado |
| T-02 | Fallback de descoberta por rota de saída | ✅ implementado |
| T-03 | Modo mock para testes (`MOCK_EXTERNAL_IP`) | ✅ implementado |
| T-04 | Leitura do `Ext-SIP-IP` corrente via ESL | ✅ implementado |
| T-05 | Escrita atômica de `vars-external-ip.xml` | ✅ implementado |
| T-06 | Aplicação via `reloadxml` + `sofia profile upstream restart` | ✅ implementado |
| T-07 | Log estruturado JSON por ciclo | ✅ implementado |
| T-08 | Container `zenith-ip-watcher` no compose | ✅ implementado |
| T-09 | Testes unitários (`sidecar/test_watcher.py`) | ✅ implementado |

## Pendências

| # | Tarefa | Motivo | Prioridade |
|---|--------|--------|-----------|
| ~~T-10~~ | ~~Decidir se o watcher deve rodar no deploy atual~~ | ✅ **Decidido em 2026-07-27: roda no deploy atual.** Sem conflito com o GAP-NET-01 — os profiles `internal*` usam `$${local_ip}` literal; só o `upstream` consome `external_*_ip` | — concluída |
| T-11 | Verificar chamadas ativas antes do `sofia profile upstream restart` | O restart derruba ~939 gateways e as chamadas em curso no profile | Alta |
| T-12 | Backoff exponencial em falha persistente de descoberta | Hoje repete a cada `POLL_INTERVAL` indefinidamente (RNF-04) | Média |
| T-13 | Métrica Prometheus de ciclos por `acao_tomada` | Hoje só há log; não dá para alertar sobre `error` recorrente | Média |
| T-14 | Teste de integração do laço `main()` | Único ponto sem cobertura direta | Baixa |
| T-15 | Avaliar remover `SSL_VERIFY=false` como opção | Desligar a verificação expõe a descoberta de IP a MITM | Baixa |

## Invariante a proteger

Se qualquer profile `internal*` voltar a usar `$${external_sip_ip}`/`$${external_rtp_ip}`
em vez de `$${local_ip}`, o watcher passa a afetá-lo e o GAP-NET-01 reaparece. Candidato a
watch item na próxima feature que tocar em `sip_profiles/`.

## Dependências

- Requer FreeSWITCH com `mod_event_socket` acessível em `FREESWITCH_ESL_HOST:PORT`
- Requer `vars.xml` incluindo `vars-external-ip.xml` **após** os defaults
- Requer `network_mode: host` e volume `./freeswitch/conf` montado em escrita
