# Módulo: widget

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `widget/src/index.html` | UI do widget desktop | 130 |
| `widget/src/ws-client.js` | WebSocket client | - |
| `widget/src-tauri/src/main.rs` | Aplicação Tauri (Rust) | 71 |
| `widget/src-tauri/tauri.conf.json` | Configuração Tauri | 45 |

## Fluxo de Controle

### main.rs (Tauri)
- Janela sempre-on-top (320x500), transparente
- System tray com menu: "Mostrar" e "Sair"
- Fecha com hide (não quit) — minimiza para bandeja
- Estado CallState: active, call_id
- Comandos Tauri: show_on_call, hide_on_call_end, set_call_id

### index.html (UI)
- Status badge: Standby / connected / disconnected / fallback
- Botões: Copiloto (toggle), Pausar (toggle)
- Checklist de POPs dinâmico (scrollable)
- Área de transcrição em tempo real
- Alertas por severidade: warning (laranja), danger (vermelho), info (azul)
- Tema escuro com glassmorphism

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Widget sempre-on-top | `tauri.conf.json:20` | 🟢 |
| Fechar = minimizar para bandeja | `main.rs:43-45` | 🟢 |
| Transparência na janela | `tauri.conf.json:22` | 🟢 |
