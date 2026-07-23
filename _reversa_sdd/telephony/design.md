# Telephony — Design Técnico

> Atualizado em 2026-07-13 (dialplan: removidas extensions mortas que bloqueavam captura de áudio)
> Revisão anterior: 2026-06-26 (B2BUA + Registration Forwarding documentados)
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
FreeSWITCH — captura áudio dos dois lados via mod_audio_stream
    │  Stream WebSocket → FastAPI → Redis Streams → Workers (STT, IA)
```

**Por que B2BUA e não proxy SIP simples:**
- O proxy SIP encaminha SDP sem tocar no áudio — impossível capturar para transcrição
- O B2BUA termina a chamada em cada lado e a reconstrói, permitindo controle total do áudio
- `mod_audio_stream` (como `mod_audio_fork` antes dele) só funciona quando o FreeSWITCH é o ponto de terminação de mídia

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
| `internal` | 5060 | Recebe REGISTERs dos interfones/softphones (porta padrão/original) |
| `internal-7060` | 7060 | Recebe REGISTERs de ramais cadastrados como `pjsip` na VitalPBX — permite migrar um ramal trocando só o servidor SIP no aparelho, sem mudar porta (feature `006-registro-porta-vitalpbx`) 🟢 |
| `internal-5062` | 5062 | Recebe REGISTERs de ramais cadastrados em `sip`/5062 na VitalPBX, mesmo padrão de `internal-7060` (feature `006-registro-porta-vitalpbx`) 🟡 — sem ramal real validado ainda nesta porta |
| `upstream` | 5065 | Gateways de saída para o VitalPBX do cliente |

Os profiles de entrada (`internal`, `internal-7060`, `internal-5062`) e o de saída (`upstream`) são separados propositalmente: um rescan de gateways no `upstream` não afeta os REGISTERs estabelecidos em qualquer profile de entrada. Os três profiles de entrada compartilham o mesmo diretório de usuários (`directory/extensions.xml`, global) e a mesma lógica de resolução de domínio (`force-register-domain=$${domain}` — necessário porque softphones como o 3CX usam o próprio endereço/porta do servidor como domínio do REGISTER, não um campo de domínio separado). Os três devem ser atualizados em conjunto quando essa lógica mudar (ver `_reversa_forward/006-registro-porta-vitalpbx/regression-watch.md#W002`).

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

## 5. Dialplan — Extensions do contexto `default` (ordem importa)

O FreeSWITCH avalia as `<extension>` de um contexto na ordem em que aparecem no XML. Sem o atributo
`continue="true"`, a **primeira** extension cuja `<condition>` casar interrompe o processamento —
extensions seguintes no arquivo nunca são avaliadas, mesmo que também casassem.

Ordem atual (`freeswitch/conf/dialplan/default.xml`) e efeito:

1. `echo_test` — `destination_number=9196` → answer + echo (teste de sanidade de registro).
2. `local_extension` — `destination_number=^(1\d{3})$` → bridge direto entre dois ramais internos
   registrados no FreeSWITCH (`user/$1@domain`). Loopback interno, fora do escopo de gravação.
3. `zenith_audio_fork` — `destination_number=^(\d+)$` → único caminho de saída para o PBX upstream.
   Responsável apenas por `answer`, `set` das variáveis `zenith_*` (consumidas depois pelo ESLClient
   via evento `CHANNEL_ANSWER`) e `bridge`. **Não** dispara mais `uuid_audio_stream` diretamente — ver
   GAP-DIALPLAN-02 e o padrão descrito logo abaixo.
4. `manual_linkage` — `*88`.
5. `playback_filler` — `play:filler`.

**Garantia de design:** toda chamada originada por um ramal do Zenith e destinada a um número
externo (fila, ramal fora do FreeSWITCH etc.) passa obrigatoriamente por `zenith_audio_fork` — não
existe hoje nenhum caminho de bridge que pule a captura de áudio.

### Removido em 2026-07-13: `bypass_to_pbx` e `registration_forwarding`

Ambas existiam desde o commit de scaffolding inicial do projeto (`cfd12b5`, `48da5b1`) e nunca foram
documentadas em spec. Encontradas durante a primeira chamada de teste real ponta a ponta (ramal 1001
→ fila 30001), que falhou com "Server Failure":

- **`bypass_to_pbx`** casava `destination_number=^(\d+)$` **antes** de `zenith_audio_fork` no arquivo
  e, sem `continue="true"`, sempre tinha precedência — tornando `zenith_audio_fork` inalcançável para
  qualquer chamada externa desde o primeiro commit do projeto. Setava `bypass_media=true` e bridgava
  sem qualquer captura, contradizendo diretamente o design descrito na seção 1 deste documento.
- **`registration_forwarding`** casava `sip_from_user=^(\d+)$` (ou seja, qualquer chamada originada
  por um ramal registrado) e sua única ação real era `set sip_forward_host=${pbx_host}` — variável
  nunca lida em nenhum outro lugar de `freeswitch/conf/`. Sem `continue="true"`, essa extension
  interrompia o dialplan antes mesmo de chegar em `bypass_to_pbx`/`zenith_audio_fork`, fazendo a
  sessão terminar sem ser atendida nem bridgada — isso é o que produzia a falha de chamada.

Nenhuma chamada real havia sido originada antes desta data: a feature `007-audio-stream-migration`
foi validada apenas com um cliente WebSocket simulando o payload (ver commit `2f313a3`), então esse
bug nunca tinha sido exercitado por uma chamada de fato.

### Investigado em 2026-07-13/14: `uuid_audio_stream` chamado como Application em vez de API

Após remover `bypass_to_pbx`/`registration_forwarding` (GAP-DIALPLAN-01), a chamada de teste seguinte
(ramal 1001 → fila 30001) atendeu e chegou até `zenith_audio_fork`, mas caiu com
`DESTINATION_OUT_OF_ORDER` logo após o `start_dtmf()`. O log confirmou a causa:

```
[ERR] switch_core_session.c:2766 Invalid Application uuid_audio_stream
[NOTICE] switch_core_session.c:2767 Hangup ... [DESTINATION_OUT_OF_ORDER]
```

`mod_audio_stream` registra `uuid_audio_stream` como comando de **API** (confirmado via
`fs_cli -x 'show modules'` → `api,uuid_audio_stream,mod_audio_stream,...`), não como Application de
dialplan. `<action application="uuid_audio_stream" data="...">` não existe no FreeSWITCH — o padrão
usual para chamar um comando de API a partir do dialplan é o wrapper genérico
`<action application="api" data="uuid_audio_stream ...">`, normalmente fornecido por `mod_dptools`.

**Essa tentativa também falhou**, com o mesmo erro (`Invalid Application api`). Uma nova chamada de
teste confirmou: `fs_cli -x 'show application'` não lista `api` (nem `bgapi`) em nenhum módulo
carregado neste build. O conjunto de módulos em produção
(`mod_commands`, `mod_conference`, `mod_dptools`, `mod_event_socket`, `mod_sofia`, `mod_spandsp` +
`mod_audio_stream`) é minimal e não inclui essa Application, nem qualquer módulo de scripting
(`mod_lua` etc.) que pudesse contornar o problema de dentro do XML do dialplan. Conclusão: **não
existe forma de chamar um comando de API por-canal a partir do dialplan neste ambiente**, ponto.

A correção definitiva move a responsabilidade para fora do dialplan — ver "Padrão adotado" abaixo e
feature `009-api-invocation-via-esl-client`.

### Padrão adotado (2026-07-14): comandos de API por-canal sem Application disponível → ESLClient

Regra geral, não específica de `uuid_audio_stream`: sempre que um módulo do FreeSWITCH expõe uma
funcionalidade apenas como comando de **API** (não como Application de dialplan) — verificável via
`fs_cli -x 'show application'` antes de qualquer integração nova — a invocação por-chamada é feita
pelo `ESLClient` (`src/telephony/esl_client.py`), a partir do handler de evento de canal
correspondente (`_handle_channel_create`, `_handle_channel_answer`, `_handle_channel_hangup`), via
`send_api`/`send_bgapi`. O dialplan permanece responsável só por roteamento, `answer`, `bridge` e
`set` de variáveis de canal (`variable_zenith_*`) que o ESLClient lê de volta pelo evento.

No caso de `uuid_audio_stream`: `_handle_channel_answer` dispara
`uuid_audio_stream {call_id} start ws://{AUDIO_STREAM_CALLBACK_HOST}/audio-stream/{call_id} stereo 8k {...}`
via `send_bgapi`, usando `Caller-Unique-ID` e as variáveis `variable_zenith_tenant_id`/
`variable_zenith_pbx_id`/`variable_zenith_agent_extension` que já chegam nesse mesmo evento. Falha
nessa chamada é logada (WARNING estruturado) mas não interrompe a chamada — gravação é best-effort,
não pode derrubar o atendimento. Detalhe completo em
`_reversa_forward/009-api-invocation-via-esl-client/roadmap.md` (decisões D-01 a D-05).

---

## 6. Riscos e Lacunas

| ID | Severidade | Descrição |
|----|------------|-----------|
| GAP-ESL-01 | 🟡 | ESL Client não tem heartbeat explícito — reconexão só detectada após falha de comando |
| GAP-ESL-02 | 🔴 | FreeSWITCH em `network_mode: host` — sem isolamento de rede Docker |
| GAP-ESL-03 | 🟡 | CHANNEL_HANGUP não tem handler explícito no código (apenas evento escutado) |
| GAP-PROV-01 | 🔴 | `mod_xml_curl` não implementado ainda — provisionamento dinâmico pendente (ciclo futuro: `SIPExtension` + FastAPI) |
| GAP-PROV-02 | ✅ | Estratégia de importação em lote definida (2026-06-26): `scripts/import_extensions.py` lê CSV exportado do VitalPBX, gera `directory/extensions.xml` + `sip_profiles/upstream/*.xml`. Dedup: pjsip > sip. Credenciais nunca commitadas (gitignored). |
| GAP-17 | ✅ | `sip_profiles/internal.xml` corrigido (2026-06-26): TLS desativado (sem certs), `sip-port` duplicado removido (porta 5060 apenas). |
| GAP-AUDIO-01 | ✅ | Substituído `mod_audio_fork` por `mod_audio_stream` (feature `007-audio-stream-migration`) — o repositório de origem do `mod_audio_fork` foi descontinuado, não era mais questão de token. Módulo novo confirmado carregado em produção; validação end-to-end de payload pendente (ver GAP-11 em `_reversa_sdd/gaps.md`) |
| GAP-DIALPLAN-01 | ✅ | `bypass_to_pbx` e `registration_forwarding` (código morto de scaffolding, sem spec, sem `continue="true"`) interceptavam toda chamada externa antes de `zenith_audio_fork` — impediam a captura de áudio e causavam falha de chamada ("Server Failure"). Nunca detectado porque nenhuma chamada real tinha sido originada antes. Removidos em 2026-07-13 na primeira validação de chamada real ponta a ponta (ver seção 5). |
| GAP-DIALPLAN-02 | ✅ | `uuid_audio_stream` é comando de API do `mod_audio_stream`, sem Application de dialplan equivalente neste build (nem `application="uuid_audio_stream"` direto, nem o wrapper genérico `application="api"` — nenhum dos dois está registrado; `show application` confirma). Ambas as tentativas derrubavam a chamada com "Invalid Application" (`DESTINATION_OUT_OF_ORDER`). Corrigido em 2026-07-14 (feature `009-api-invocation-via-esl-client`) movendo a invocação para o `ESLClient`, disparada via `send_bgapi` a partir de `_handle_channel_answer` — ver seção 5, "Padrão adotado". |
| GAP-DIALPLAN-03 | ✅ | `zenith_audio_fork` bridgava com `sofia/external/${destination_number}@${pbx_host}` — o profile `external` **nunca existiu** neste FreeSWITCH (`sofia status` só lista `internal`, `internal-7060`, `internal-5062`, `upstream`); todo `bridge` falhava com `[ERR] Invalid Profile` (`INVALID_PROFILE`). Mascarado desde o commit inicial (`cfd12b5`) pelos GAP-DIALPLAN-01 e -02, que sempre derrubavam a chamada antes de alcançar o `bridge`. Só ficou visível em 2026-07-14 ao validar a feature `009-api-invocation-via-esl-client` ponta a ponta. Corrigido trocando para `sofia/gateway/upstream-${sip_from_user}/${destination_number}` — usa o gateway já registrado individualmente para cada ramal (ver "Papel do FreeSWITCH" em `_reversa_sdd/architecture.md`), consistente com o desenho de B2BUA por-ramal do projeto. |
| GAP-DIALPLAN-04 | ✅ | `zenith_audio_fork` fazia `set` das variáveis `zenith_*` **depois** de `answer()` — mas o evento `CHANNEL_ANSWER` dispara no exato momento do `answer()`, então nenhuma variável `zenith_*` jamais chegou populada no evento que o ESLClient escuta (`variable_zenith_tenant_id` sempre vazio). Isso, sozinho, impediu `create_call_record`/captura de áudio de rodar em QUALQUER chamada desde o início do projeto, independente de qualquer outro GAP. Corrigido em 2026-07-14 (feature `010-record-real-call-audio-e2e`) reordenando: todos os `set` antes do `answer()`. |
| GAP-VARS-01 | ✅ | `zenith_tenant_id=${tenant_id}` e `zenith_pbx_id=${pbx_id}` no dialplan usavam substituição de variável de canal (`${...}`, um cifrão), mas `tenant_id`/`pbx_id` só existem como variáveis globais de pré-processador (`X-PRE-PROCESS cmd="set"` em `vars.xml`), acessíveis apenas via `$${...}` (dois cifrões, resolvido na carga do XML). `${tenant_id}` sempre resolvia vazio. Corrigido trocando para `$${tenant_id}`/`$${pbx_id}` — confirmado via `fs_cli -x 'xml_locate dialplan'` que o valor literal (`akom`) fica gravado no XML carregado. |
| GAP-ESL-04 | ✅ | `ESLClient._read_events` usava timeout de 30s no `read()` da conexão de eventos; sem heartbeat do FreeSWITCH em conexão ociosa, isso derrubava e reconectava a conexão ESL a cada ~30-40s mesmo sem problema real, criando janelas onde eventos reais (`CHANNEL_ANSWER`) podiam chegar e se perder. Corrigido aumentando o timeout para 300s — desconexão real já é detectada por `read()` retornar vazio (EOF), não precisa de timeout curto. |
| GAP-ESL-05 | ✅ | `ESLClient._read_events`/`_process_event` faziam split ingênuo do stream por `"\n\n"`, mas o protocolo ESL real é `Content-Length: N\n\n` + corpo de exatamente N bytes — todo evento de canal real (`CHANNEL_ANSWER`/`CHANNEL_CREATE`/`CHANNEL_HANGUP`) chegava mas era descartado como "non-JSON" por causa do corte errado do corpo. Bug presente desde a implementação original do ESLClient. Corrigido implementando o framing correto por `Content-Length` em `_read_events`. |
| GAP-ESL-06 | ✅ | `send_api`/`send_bgapi` liam a resposta do comando na **mesma conexão TCP** que o loop de eventos lê continuamente — quando chamados de dentro de um handler de evento (ex: `_start_audio_capture` a partir de `_handle_channel_answer`), a leitura da resposta podia se misturar com o próximo evento na fila, causando falha intermitente e silenciosa do disparo de `uuid_audio_stream`. Corrigido com uma segunda conexão ESL dedicada só a comandos (`_connect_command`/`_send_command`), separada da conexão de eventos. |
| GAP-ESL-07 | ✅ | `connect()`/`_connect_command()` não consumiam a saudação inicial do ESL (`Content-Type: auth/request\n\n`, enviada pelo FreeSWITCH assim que a conexão abre) antes de mandar `auth`, causando corrida de leitura que às vezes interpretava a saudação como resposta de autenticação falha. Corrigido lendo e descartando a saudação antes de enviar `auth`. |
| GAP-DB-01 | ✅ | `get_tenant_db` criava uma `AsyncSession` vinculada a uma `Connection` obtida via `engine.connect()` (com autobegin implícito pelo `SET search_path`); `session.commit()` finalizava a transação lógica do ORM mas não commitava a `Connection` em si — ao sair do `async with engine.connect()` sem commit explícito, tudo era revertido silenciosamente (sem exceção). Nenhum `Call` jamais foi persistido no banco antes desta correção, em nenhuma chamada real de nenhuma feature anterior. Corrigido com `await conn.commit()` explícito após o trabalho da sessão. |
| GAP-WS-01 | ✅ | `AudioIngestor.handle_forked_stream` usava `websocket.receive_bytes()` em loop, mas `mod_audio_stream` manda um frame de texto (JSON de controle) na conexão antes do áudio binário — isso derrubava a conexão com `KeyError: 'bytes'` assim que `mod_audio_stream` conectava de verdade (nunca exercitado antes por nenhuma chamada real). Corrigido usando `websocket.receive()` genérico, distinguindo frame de texto (ignorado) de frame binário (áudio). |
| GAP-ESL-08 | ✅ | `_start_audio_capture` disparava incondicionalmente em `_handle_channel_answer`, sem o mesmo guard `if tenant_id:` de `create_call_record` — como `CHANNEL_ANSWER` dispara para as duas pernas de uma chamada bridgeada (a-leg e b-leg), isso iniciava duas capturas de áudio simultâneas por chamada (uma órfã, sem tenant). Corrigido movendo `_start_audio_capture` para dentro do `if tenant_id:`. |
| GAP-NET-01 | 🔴 | Toda a cadeia de software (dialplan → ESLClient → `uuid_audio_stream` → WebSocket → gravação → banco) está confirmada funcionando ponta a ponta (2026-07-14/15, feature `010-record-real-call-audio-e2e`), mas o áudio capturado é silêncio digital puro (RMS ≈ -90dB). Packet capture confirma apenas 1 pacote RTP em ~6s de chamada — sinalização SIP perfeita (INVITE/180/200), mas mídia RTP não flui. FreeSWITCH anuncia `Ext-RTP-IP=200.170.149.139` (IP público) enquanto a interface real é `10.10.10.11`; suspeita de bloqueio no roteador Mikrotik para a faixa de portas RTP (mesmo padrão do incidente de sinalização SIP corrigido em 2026-07-08, ver `_reversa_sdd/telephony/packet-capture-debug.md`, mas dessa vez afetando mídia, não sinalização). Requer acesso ao Mikrotik — fora do escopo do código deste repositório. **Atualização 2026-07-23** (após GAP-24 resolver o módulo ausente): usuário revisou o firewall do Mikrotik e não encontrou regra de bloqueio. Nova captura (chamada real >10s, 1001→3173001) mostra só 2 pacotes RTP em toda a chamada, os dois **saindo** do FreeSWITCH, nenhum de volta em nenhuma perna: (1) perna FreeSWITCH↔VitalPBX com SDP limpo dos dois lados (`200.170.149.139:29398` ↔ `177.71.153.68:18508`, sem NAT), mesmo assim sem retorno; (2) perna 1001↔FreeSWITCH — o softphone 3CX do ramal 1001 anuncia seu **IP privado** `192.168.50.92` no SDP (`o=3cxVCE ... IN IP4 192.168.50.92`); o profile `internal` já tem `apply-nat-acl=rfc1918` + `aggressive-nat-detection`/`rtp-auto-adjust` habilitados, mas isso só corrige depois de receber ao menos um pacote RTP de entrada do telefone — que não chegou. RTP praticamente nulo nas duas pernas simultaneamente aponta para algo mais estrutural que "Mikrotik bloqueia" ou "VitalPBX não responde" isoladamente; ainda requer investigação de rede (fora do escopo de código), possivelmente NAT/conntrack UDP não cobrindo a faixa RTP dinâmica mesmo sem regra de bloqueio explícita. |
