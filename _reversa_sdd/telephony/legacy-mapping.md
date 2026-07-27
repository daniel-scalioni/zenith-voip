# Módulo: telephony

> Gerado pelo Archaeologist — 2026-06-19
> **Re-extração incremental — 2026-07-27** (base `48da5b1` → `0658157`, delta D-01/D-12)
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/telephony/esl_client.py` | Cliente FreeSWITCH ESL (Event Socket Layer) | 319 |
| `src/telephony/filler_audio.py` | Áudio de preenchimento em chamadas | 20 |
| `src/telephony/whisper_mode.py` | Modo Whisper (TTS no canal do agente) | 24 |

> `esl_client.py` cresceu de 206 → 319 linhas na re-extração. É o arquivo com maior
> divergência em relação à extração de 2026-06-19.

## Fluxo de Controle

### esl_client.py — Core

- `ESLClient` gerencia **duas conexões TCP independentes** com o FreeSWITCH ESL:
  - **conexão de eventos** (`reader`/`writer`) — só escuta o event stream;
  - **conexão de comandos** (`_cmd_reader`/`_cmd_writer`, serializada por `_cmd_lock`) —
    exclusiva para `api`/`bgapi`. 🆕 2026-07
- `connect()` (`esl_client.py:38`) → **consome a saudação `auth/request`** que o FreeSWITCH
  envia sozinho ao abrir o socket, só então autentica e faz o subscribe em eventos JSON. 🆕
- `_connect_command()` (`esl_client.py:58`) → mesma sequência para o socket de comandos.
- `_send_command(prefix, command, timeout)` (`esl_client.py:71`) → ponto único de escrita
  de comandos; invalida `_cmd_writer` em erro para forçar reconexão no próximo uso. 🆕
- `send_api(command)` (`esl_client.py:84`) → delega a `_send_command("api", ..., 10.0s)`.
- `send_bgapi(command)` (`esl_client.py:87`) → delega a `_send_command("bgapi", ..., 5.0s)`.
- `start_event_listener()` (`esl_client.py:101`) → task assíncrona de event loop.
- `_event_loop()` (`esl_client.py:113`) → loop de reconexão automática com backoff de 2s.
- `_read_events()` (`esl_client.py:125`) → **parser de framing ESL correto**: lê o bloco de
  headers até a linha em branco, extrai `Content-Length` e consome exatamente esse número de
  bytes do corpo. Substituiu o `split("\n\n")` anterior, que corrompia eventos cujo JSON
  contivesse a sequência delimitadora. Buffer passou de `str` para `bytes`. 🆕
- `_process_event()` (`esl_client.py:157`) → roteia eventos, **loga o nome do evento** e
  encapsula cada handler em `try/except` com `logger.exception` (preserva `CancelledError`).

Eventos escutados: `CHANNEL_CREATE`, `CHANNEL_ANSWER`, **`CHANNEL_HANGUP`** 🆕,
`SOFIA_REGISTER`, `SOFIA_UNREGISTER`.

### Handlers de Eventos ESL

- `_handle_register()` (`:183`) → mapeia SIP user → IP no Redis (TTL 3600s)
- `_handle_unregister()` (`:193`) → remove mapeamento SIP do Redis
- `_handle_channel_create()` (`:198`) → detecta `*88` para manual linkage
- `_handle_channel_answer()` (`:203`) → registra metadados no `audio_ingestor`, **cria a
  linha `Call` no schema do tenant** (`create_call_record`) e **dispara a captura de áudio**. 🆕
- `_start_audio_capture(call_id)` (`:228`) 🆕 → monta
  `uuid_audio_stream <call_id> start ws://<AUDIO_STREAM_CALLBACK_HOST>/audio-stream/<call_id> stereo 8k <metadata>`
  e envia por `bgapi`; loga warning se a resposta contiver `-ERR` ou não contiver `+OK`.
- `_handle_channel_hangup()` (`:240`) 🆕 → finaliza a linha `Call` (`finalize_call_record`),
  esvazia `audio_ingestor.buffers[call_id]`, agrupa os chunks por canal (`tx`/`rx`) e
  enfileira o job `upload_recording_batch` via `enqueue_recording_upload`.
- `_handle_manual_linkage()` (`:261`)

### Whisper Mode
- `WhisperMode.whisper_to_agent()` → sintetiza TTS e toca no canal do agente via `uuid_play`

### Filler Audio
- `FillerAudio.play_to_customer()` → toca áudio de espera no canal do cliente

## Algoritmos

**SIP IP Extraction** (`_extract_ip`, `:279`): extrai IP do evento ESL de múltiplos campos
(`sip_network_ip`, `Caller-Network-Addr`, `sip_via_host`, `Caller-Source`) com regex fallback.

**Reconexão Automática**: em erro de conexão, aguarda 2s e reconecta (`:121`).

**Framing ESL por Content-Length** 🆕: ver `_read_events()` acima. O timeout de leitura do
event stream subiu de **30s para 300s** — o FreeSWITCH não envia heartbeat em conexão ociosa,
e o timeout curto derrubava/reconectava a cada janela sem chamada, abrindo um gap onde um
`CHANNEL_ANSWER` real podia se perder. Desconexão real continua detectada por EOF (`read()`
retornando vazio).

## Configuração FreeSWITCH (delta D-12)

| Item | Antes (2026-06) | Agora (2026-07) |
|---|---|---|
| Módulo de captura | `mod_audio_fork` | **`mod_audio_stream`** (repo do fork foi descontinuado) |
| Módulo ESL | `mod_esl` | **`mod_event_socket`** |
| Imagem | `safarov/freeswitch:1.10.12` | **build próprio** (`freeswitch/Dockerfile`, `.deb` vendorizados) |
| Disparo da captura | ação no dialplan | **`bgapi uuid_audio_stream` pelo ESLClient** |
| SIP profiles | `internal`, `upstream/upstream-{ext}.xml` | + **`internal-5062`, `internal-7060`, `upstream.xml`** |
| Configs novas | — | `acl.conf.xml`, `event_socket.conf.xml`, `sofia.conf.xml`, `directory/default.xml`, **`vars.xml`** |

**`freeswitch/conf/vars.xml`** (novo) define `local_ip_v4=auto`, `external_sip_ip`/
`external_rtp_ip` = `$${local_ip}` (fix do GAP-NET-01 — IP público fixo quebrava peers da
rede local), `domain=zenith.local`, `pbx_host=sip.maisalerta.tecnorise.com` e os valores
fixos do tenant Akom (`tenant_id`, `pbx_id`). O include de `vars-external-ip.xml` é
sobrescrito em runtime pelo sidecar `ip-watcher` (ver módulo `sidecar`).

**Dialplan** (`freeswitch/conf/dialplan/default.xml`): as extensões
`registration_forwarding` e `bypass_to_pbx` foram removidas; entraram `echo_test` (disque
`9196`) e `local_extension` (`^1\d{3}$` → `user/$1@$${domain}`). A extensão
`zenith_audio_fork` deixou de invocar `mod_audio_fork` e passou a fazer
`bridge sofia/gateway/upstream-${sip_from_user}/${destination_number}`, com as variáveis
`zenith_tenant_id`/`zenith_pbx_id` lidas de `$${...}` (globais) em vez de `${...}` (canal) —
esta era a causa de elas nunca chegarem populadas ao ESL.

## Mapeamentos Redis

| Chave | TTL | Descrição |
|-------|-----|-----------|
| zenith:sip:ip_to_extension:{ip} | 3600s | IP → ramal SIP |
| zenith:sip:extension_to_ip:{extension} | 3600s | Ramal SIP → IP |
| zenith:sip:extension_to_pbx:{extension} | - | Ramal → PBX (inserido externamente) |
| zenith:ws:agent_session:{agent_uuid} | 30-120s | Sessão WebSocket do agente |

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Reconexão automática com backoff de 2s | `esl_client.py:121` | 🟢 |
| `*88` é código de linkage manual | `esl_client.py:200` | 🟢 |
| SIP mappings expiram em 1h | `esl_client.py:288-294` | 🟢 |
| Mapeamento UUID mantido em memória | `esl_client.py:26,90-99` | 🟢 |
| 🆕 Comandos ESL usam socket próprio, nunca o do event stream | `esl_client.py:58-82` | 🟢 |
| 🆕 Captura de áudio só começa no CHANNEL_ANSWER, disparada pela API (não pelo dialplan) | `esl_client.py:224,228` | 🟢 |
| 🆕 Linha `Call` só é criada se `tenant_id` vier populado no evento | `esl_client.py:219` | 🟢 |
| 🆕 Gravação só é enfileirada se houver chunks no buffer | `esl_client.py:251-253` | 🟢 |
| 🆕 Falha de handler não derruba o event loop (log + segue) | `esl_client.py:176-181` | 🟢 |

## Dependências removidas

`greenswitch==1.1.0` saiu do `requirements.txt` (delta D-15). O ESL é falado por socket
TCP bruto com `asyncio` — a extração anterior listava `greenswitch` como dependência ativa
do módulo, o que **não é mais verdade**.
