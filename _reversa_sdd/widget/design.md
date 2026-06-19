# Widget, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

### WebSocket Messages (Recebidas)

| Tipo | Payload | Descrição |
|------|---------|-----------|
| transcript | `{channel, text, confidence}` | Transcrição em tempo real |
| alert | `{severity, message}` | Alerta de anomalia |
| insight | `{entities, pops, summary}` | Insight processado |
| status | `{stt_status, connection}` | Status da conexão |

### WebSocket Messages (Enviadas)

| Tipo | Payload | Descrição |
|------|---------|-----------|
| ping | `{}` | Heartbeat |
| linkage | `{code: "*88"}` | Linkage manual |

## Fluxo Principal

1. Tauri app inicia e conecta WebSocket — `widget/src/ws-client.js:10-20`
2. Se desconectar, tenta reconexão a cada 3s — `widget/src/ws-client.js:33`
3. Mensagens transcript exibidas na UI em tempo real — `widget/src/index.html:50-70`
4. Alertas de anomalia exibidos com severidade (warning/danger) — `widget/src/index.html:80-95`
5. POPs checklist renderizado para o operador — `widget/src/index.html:100-115`
6. Copiloto mostra sugestões baseadas no contexto — `widget/src/index.html:120-130`

## Estados do Widget

| Estado | Descrição |
|--------|-----------|
| 🟢 Online | Conectado e operacional |
| 🟡 Deepgram/Fallback | STT em fallback |
| ⚠ Erro | Erro de conexão |
| 🔴 Desconectado | WebSocket desconectado (reconnect em 3s) |

## Riscos e Lacunas

- 🟡 UI sem testes automatizados
- 🟡 Sem fallback se WebSocket não conectar (loop infinito de reconexão)
