# Widget — Desktop Widget

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Aplicação desktop Tauri (Rust + HTML/JS) para operadores: sempre-on-top, 320x500, transparente, com WebSocket client para agent assist.

## Responsabilidades

- Exibir status da conexão (standby/connected/disconnected/fallback)
- Mostrar transcrição em tempo real
- Exibir alertas de anomalia
- Checklist de POPs
- Copiloto com sugestões
- System tray com Mostrar/Sair

## Regras de Negócio

- Widget sempre-on-top 🟢
- Fechar = minimizar para bandeja 🟢
- Auto-reconnect a cada 3s em caso de desconexão 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Exibir status da conexão WebSocket | Must |
| RF-02 | Exibir transcrição em tempo real | Must |
| RF-03 | Exibir alertas de anomalia | Must |
| RF-04 | Exibir checklist de POPs | Should |
| RF-05 | Copiloto com sugestões | Should |
| RF-06 | System tray com Mostrar/Sair | Must |
| RF-07 | Auto-reconnect WebSocket a cada 3s | Must |

## Rastreabilidade

| Arquivo | Função | Cobertura |
|---------|--------|-----------|
| `widget/src/index.html` | UI | 🟢 |
| `widget/src/ws-client.js` | WebSocket client | 🟢 |
| `widget/src-tauri/src/main.rs` | Tauri app | 🟢 |
| `widget/src-tauri/tauri.conf.json` | Config | 🟢 |
