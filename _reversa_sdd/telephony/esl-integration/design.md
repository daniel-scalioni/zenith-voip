# ESL Integration, Design

**Interface:** `connect() → None`, `send_api(command) → str`
**Eventos:** CHANNEL_CREATE, CHANNEL_ANSWER, CHANNEL_HANGUP
**Redis:** `zenith:sip:ip_to_extension:{ip}` e `zenith:sip:extension_to_ip:{ext}` TTL 3600s
**Auto-reconnect:** backoff 2s em caso de desconexão
**Origem:** `src/telephony/esl_client.py:30-184` 🟢
