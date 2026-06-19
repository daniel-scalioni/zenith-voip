# Widget, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar UI do widget (HTML/CSS)
  - Origem: `widget/src/index.html`
  - Critério: status, transcrição, alertas, POPs, copiloto visíveis
  - Confiança: 🟢

- [ ] T-02, Implementar WebSocket client com auto-reconnect
  - Origem: `widget/src/ws-client.js:10-33`
  - Critério: conexão estabelecida; reconexão a cada 3s
  - Confiança: 🟢

- [ ] T-03, Implementar Tauri app (Rust) com system tray
  - Origem: `widget/src-tauri/src/main.rs`
  - Critério: sempre-on-top, 320x500, transparente; fechar minimiza para bandeja
  - Confiança: 🟢

- [ ] T-04, Implementar heartbeat/ping
  - Origem: `widget/src/ws-client.js:35-40`
  - Critério: ping periódico mantém conexão ativa
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar conexão WebSocket
- [ ] TT-02, Testar reconexão automática
- [ ] TT-03, Testar renderização de transcrição
- [ ] TT-04, Testar system tray (mostrar/sair)
