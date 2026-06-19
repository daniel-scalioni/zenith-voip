# Desktop Widget, Design

**Tecnologia:** Tauri (Rust backend + HTML/JS frontend), 320x500, transparente
**Estados:** 🟢 Online, 🟡 Fallback, ⚠ Erro, 🔴 Desconectado
**WebSocket:** WSS `/ws/{call_id}` com auto-reconnect 3s
**Origem:** `widget/src/index.html`, `widget/src/ws-client.js`, `widget/src-tauri/src/main.rs` 🟢
