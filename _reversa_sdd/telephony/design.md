# Telephony — Design Técnico

> Atualizado em 2026-06-26 (revisão arquitetural: B2BUA + Registration Forwarding documentados)
> Gerado originalmente pelo Writer — 2026-06-19

---

## 1. Topologia SIP: B2BUA com Registration Forwarding

Este é o padrão arquitetural central do Zenith. O FreeSWITCH atua como **B2BUA (Back-to-Back User Agent)** posicionado entre os interfones/softphones e o PBX de produção do cliente (VitalPBX / GPhone).

```
Interfone / Softphone
    │  REGISTER ext=1001, senha=XXXX → sip:freeswitch:5060
    ▼
FreeSWITCH — profile "internal" (porta 5060)
    │  Aceita o REGISTER do interfone
    │  Re-registra upstream: REGISTER ext=1001, senha=XXXX → sip.maisalerta.tecnorise.com
    ▼
VitalPBX (GPhone) — sip.maisalerta.tecnorise.com
    │  Enxerga ramal 1001 como "registrado" (via FreeSWITCH, transparente)
    │  Sistemas satélite veem o ramal como online normalmente
    ▼
FreeSWITCH — captura áudio dos dois lados via mod_audio_fork
    │  Stream WebSocket → FastAPI → Redis Streams → Workers (STT, IA)
```

**Por que B2BUA e não proxy SIP simples:**
- O proxy SIP encaminha SDP sem tocar no áudio — impossível capturar para transcrição
- O B2BUA termina a chamada em cada lado e a reconstrói, permitindo controle total do áudio
- `mod_audio_fork` só funciona quando o FreeSWITCH é o ponto de terminação de mídia

**Garantia de visibilidade no VitalPBX:**
O VitalPBX e seus sistemas satélite (portaria, integrações externas) dependem de ver os ramais como "registrados". Com o B2BUA, o FreeSWITCH registra *em nome* de cada ramal — o VitalPBX nunca sabe que há um intermediário.

---

## 2. Provisionamento Dinâmico — mod_xml_curl

Com centenas a milhares de ramais por tenant, gerenciar arquivos XML por ramal é inviável. A solução é **`mod_xml_curl`**: o FreeSWITCH consulta a API do Zenith para obter configurações de diretório e gateways sob demanda.

```
FreeSWITCH precisa de info sobre ramal 1001
    │ GET /freeswitch/directory?user=1001&domain=tenant.local
    ▼
FastAPI Zenith
    │ SELECT * FROM sip_extensions WHERE extension='1001' AND tenant_id=X
    ▼
PostgreSQL (schema do tenant)
    │ Retorna: usuário, senha, gateway upstream, variáveis de canal
    ▼
FreeSWITCH: sem restart, sem arquivo novo — usa as credenciais imediatamente
```

**Consequências:**
- Novo ramal no GPhone → cadastrar no admin Zenith → FreeSWITCH enxerga na próxima requisição
- Para 1000 ramais iniciais: importação em lote (CSV exportado do VitalPBX)
- A tabela `SIPExtension` no banco Zenith é a **fonte de verdade** dos ramais

**Modelo de dados (schema por tenant):**
```
sip_extensions
  id            UUID PK
  extension     VARCHAR (ex: "1001")
  sip_password  VARCHAR (armazenada cifrada)
  display_name  VARCHAR
  pbx_id        FK → public.pbxs
  active        BOOLEAN
  created_at    TIMESTAMP
```

A senha SIP é armazenada cifrada no banco e nunca exposta em logs ou arquivos de configuração. O endpoint `/freeswitch/directory` é acessível apenas internamente (rede Docker, sem exposição externa).

---

## 3. Perfis SIP do FreeSWITCH

| Profile | Porta | Função |
|---------|-------|--------|
| `internal` | 5060 | Recebe REGISTERs dos interfones/softphones |
| `upstream` | 5065 | Gateways de saída para o VitalPBX do cliente |

Os dois profiles são separados propositalmente: um rescan de gateways no `upstream` não afeta os REGISTERs estabelecidos no `internal`.

### Porta de destino no VitalPBX (por tecnologia)

O VitalPBX expõe perfis SIP distintos em portas diferentes. A tecnologia usada por cada ramal
está no CSV de exportação (coluna `technology`):

| Tecnologia (`technology`) | Porta no VitalPBX |
|---------------------------|-------------------|
| `pjsip`                   | 7060              |
| `sip`                     | 5060 ou 5062 (depende do perfil — verificar por ramal) |

A coluna `technology` do CSV deve ser preservada no registro de cada ramal para que o gateway
seja gerado com o `proxy` correto incluindo a porta. O `import_extensions.py` usa o campo `tech`
do dict de extensão para determinar a porta de destino.

**Gateway por ramal (gerado pelo `import_extensions.py`):**
```xml
<gateway name="upstream-{extension}">
  <param name="username" value="{extension}"/>
  <param name="password" value="{sip_password}"/>
  <param name="proxy" value="{pbx_host}:{port_by_tech}"/>  <!-- ex: sip.maisalerta.tecnorise.com:7060 -->
  <param name="register" value="true"/>
  <param name="caller-id-in-from" value="true"/>
  <param name="ping" value="25"/>
</gateway>
```

---

## 4. Interface ESL (ESL Client — código existente)

| Símbolo | Assinatura | Retorno |
|---------|-----------|---------|
| `connect` | `()` | `None` (conexão ESL) |
| `send_api` | `(command: str)` | `str` |
| `whisper_to_agent` | `(call_id: str, text: str)` | `dict` |

### Fluxo de eventos ESL

1. `connect()` estabelece conexão ESL com FreeSWITCH — `src/telephony/esl_client.py:30-45`
2. Se conexão cair, auto-reconnect com backoff de 2s — `src/telephony/esl_client.py:86-88`
3. Eventos ESL recebidos: CHANNEL_CREATE → CHANNEL_ANSWER → CHANNEL_HANGUP
4. No CHANNEL_ANSWER, extrai IP do agente e mapeia no Redis — `src/telephony/esl_client.py:139-149`
5. `zenith:sip:ip_to_extension:{ip}` e `zenith:sip:extension_to_ip:{ext}` criados com TTL 3600s — `src/telephony/esl_client.py:179-184`
6. Código `*88` detectado → cria sessão "awaiting_linkage" — `src/telephony/esl_client.py:136-137`
7. Whisper mode: `whisper_to_agent()` envia TTS para canal do agente — `src/telephony/whisper_mode.py:15-30`
8. Filler audio tocado para cliente enquanto sistema processa — `src/telephony/filler_audio.py:10-25`

### Máquina de Estados (ESL Connection)

```
disconnected → connecting → connected
                  ↓
         reconnect (backoff 2s)
```

---

## 5. Riscos e Lacunas

| ID | Severidade | Descrição |
|----|------------|-----------|
| GAP-ESL-01 | 🟡 | ESL Client não tem heartbeat explícito — reconexão só detectada após falha de comando |
| GAP-ESL-02 | 🔴 | FreeSWITCH em `network_mode: host` — sem isolamento de rede Docker |
| GAP-ESL-03 | 🟡 | CHANNEL_HANGUP não tem handler explícito no código (apenas evento escutado) |
| GAP-PROV-01 | 🔴 | `mod_xml_curl` não implementado ainda — provisionamento dinâmico pendente (ciclo futuro: `SIPExtension` + FastAPI) |
| GAP-PROV-02 | ✅ | Estratégia de importação em lote definida (2026-06-26): `scripts/import_extensions.py` lê CSV exportado do VitalPBX, gera `directory/extensions.xml` + `sip_profiles/upstream/*.xml`. Dedup: pjsip > sip. Credenciais nunca commitadas (gitignored). |
| GAP-17 | ✅ | `sip_profiles/internal.xml` corrigido (2026-06-26): TLS desativado (sem certs), `sip-port` duplicado removido (porta 5060 apenas). |
| GAP-AUDIO-01 | 🔴 | `mod_audio_fork` requer build customizado bloqueado por token SignalWire inválido (GAP-11) |
