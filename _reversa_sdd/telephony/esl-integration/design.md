# ESL Integration, Design

**Interface:** `connect() → None`, `start_event_listener() → None`, `send_api(command) → str`
**Eventos:** CHANNEL_CREATE, CHANNEL_ANSWER, CHANNEL_HANGUP
**Redis:** `zenith:sip:ip_to_extension:{ip}` e `zenith:sip:extension_to_ip:{ext}` TTL 3600s
**Auto-reconnect:** backoff 2s em caso de desconexão (`_event_loop`, reconecta sozinho se `self.connected` for `False`)
**Origem:** `src/telephony/esl_client.py` 🟢

**Startup (2026-07-12, GAP-23):** `esl_client.start_event_listener()` é chamado no `lifespan` de `src/main.py`, **somente quando `INSTANCE_ID == 1`** — evita que `fastapi-1` e `fastapi-2` processem o mesmo evento ESL em duplicidade (`create_call_record` não é idempotente). Antes desta correção, `esl_client` nunca era conectado por nenhum código da aplicação — instanciado (`esl_client = ESLClient()`, padrão singleton de módulo) mas nunca iniciado, então `CHANNEL_ANSWER`/`CHANNEL_HANGUP` nunca eram processados para chamadas reais.
