# Lacunas Identificadas — zenith-voip

> Gerado pelo Revisor em 2026-06-19
> Categorizadas por severidade

---

## Críticas (bloqueiam reimplementação)

| ID | Módulo | Descrição | Spec afetada | Status |
|----|--------|-----------|-------------|--------|
| GAP-01 | `audio` | `_detect_channel()` é stub — canal RX nunca detectado. Investigação (2026-06-19) mostrou que o protocolo real (`mod_audio_fork` stereo) intercala os dois canais no mesmo frame PCM16 — corrigido para de-interleaving em `src/audio/ingestor.py`. Convenção de qual canal é tx/rx ainda não validada contra FreeSWITCH real (🟡, ver `audio/design.md`) | `audio/requirements.md` | Parcialmente resolvida |
| GAP-02 | `workers` | `analyze_sentiment()` e `audit_procedure()` são stubs | `workers/requirements.md` | Aberta |

| GAP-11 | `infra` | Imagem `safarov/freeswitch:1.10.12` usada em `docker-compose.app.yml` **não contém `mod_audio_fork` compilado** — a gravação via fork de áudio não funcionava sem build customizado do módulo (`drachtio-freeswitch-modules`) | `infra/deployment` | ✅ Resolvida (2026-07-10, features `007-audio-stream-migration` + `008-piper-tts-standalone`) — `drachtio-freeswitch-modules` foi descontinuado; substituído por `mod_audio_stream` (`amigniter/mod_audio_stream`, MIT, ativo), build customizado sem depender do repositório SignalWire estar sempre disponível (`.deb` vendorizados). `zenith-api-1` buildado e rodando `healthy` pela primeira vez neste host (após GAP-18 remover os bloqueios de `requirements.txt`). Validação end-to-end feita via cliente WebSocket direto simulando o payload de `mod_audio_stream`: Redis Streams confirmou de-interleaving correto tx/rx. Gap adicional descoberto e corrigido no processo: a rota WebSocket `/audio-stream` nunca tinha sido registrada em `src/main.py` (`AudioIngestor.handle_forked_stream` existia mas não estava conectado a nenhum endpoint) — corrigido como `/audio-stream/{call_id}`. Também corrigido: FreeSWITCH roda em `network_mode: host` e não resolvia `zenith-api-1` por DNS de container — dialplan agora usa `${zenith_api_host}` (`127.0.0.1:8001`, `vars.xml`) |
| GAP-16 | `infra` | `freeswitch/conf/` não tinha config raiz bootável (faltavam `vars.xml`, `freeswitch.xml`, `acl.conf.xml`, `autoload_configs/event_socket.conf.xml`, `autoload_configs/sofia.conf.xml`, `directory/default.xml`) — container provavelmente não subia. Também: `modules.conf.xml` carregava `mod_esl` (módulo inexistente no FreeSWITCH; o módulo real do Event Socket é `mod_event_socket`) | `infra/deployment` | ✅ Resolvida (2026-06-24) — config completada e validada com boot real estável (90s observados, `RestartCount=0`) em `10.10.10.11`. Ver `_reversa_forward/004-bootstrap-freeswitch/` |
| GAP-17 | `infra`/`telephony` | `sip_profiles/internal.xml` declarava dois `<param name="sip-port">` (5060 e 5061) e referenciava certs TLS em `/etc/freeswitch/tls/` (inexistente) | `telephony/design.md` | ✅ Resolvida (2026-06-26) — TLS desativado (comentado), porta duplicada removida; profile `internal` vincula apenas porta 5060 |
| GAP-PROV-01 | `telephony` | `mod_xml_curl` não implementado — provisionamento dinâmico de ramais no FreeSWITCH ainda não existe | `telephony/design.md` | Aberta — ciclo futuro (`SIPExtension` + FastAPI + admin UI) |
| GAP-PROV-02 | `telephony` | Estratégia de importação em lote dos ramais do VitalPBX para o FreeSWITCH não definida | `telephony/design.md` | ✅ Resolvida (2026-06-26) — `scripts/import_extensions.py` lê CSV exportado do VitalPBX, gera `directory/extensions.xml` + `sip_profiles/upstream/*.xml`; dedup pjsip > sip; credenciais gitignored |
| GAP-UPSTREAM-01 | `telephony`/`infra` | 939 gateways upstream em **FAIL_WAIT** após deploy em 2026-06-29 — FreeSWITCH tenta registrar ramais no VitalPBX (`sip.maisalerta.tecnorise.com`) mas recebe rejeição. Causas prováveis: (1) IP `10.10.10.11` não liberado no firewall/whitelist do VitalPBX para registros SIP; (2) senhas do CSV divergem das configuradas no VitalPBX. Usuário não tem acesso admin ao VitalPBX — necessário acionar administrador para liberar IP | `telephony/design.md`, `infra/deployment/design.md` | ✅ Resolvida (confirmado em 2026-07-08, feature `006-registro-porta-vitalpbx`) — IP público `200.170.149.139` liberado no VitalPBX (feature `005-dynamic-external-ip`); `sofia status gateway upstream::upstream-1001` mostra `State: REGED`, `Status: UP (ping)`, uptime de ~10h no momento da verificação |
| GAP-12 | `telephony`/`database` | Nenhum handler de `CHANNEL_HANGUP` existia e nenhuma linha `Call` era criada em ponto algum do fluxo real (só em teste de schema) — gravação não tinha como ser persistida nem finalizada. Implementado `_handle_channel_hangup` + `src/services/calls.py` (cria `Call` no answer, finaliza no hangup, enfileira upload dos buffers) | `telephony/design.md`, `database/design.md` | Parcialmente resolvida — lógica testada via mocks (`tests/test_call_lifecycle.py`), pendente validação com Postgres/Redis reais |
| GAP-13 | `database` | `Call.metadata`, `Transcript.metadata` e `CallInsight.metadata` colidiam com o atributo reservado `metadata` do SQLAlchemy declarative, quebrando a importação de `src.database.database` (e `tests/test_multitenancy.py`) | `database/design.md` | ✅ Resolvida — renomeado para `extra_metadata` (coluna no banco continua `metadata`) |
| GAP-14 | `infra`/`workers` | Nenhum container do `docker-compose.app.yml` processava o job `upload_recording_batch` (só existia `arq-cleanup` para `audio_cleanup.WorkerSettings`) — mesmo com upload corrigido, a gravação nunca seria persistida. Adicionado serviço `arq-uploader` | `infra/deployment`, `workers/audio-upload` | ✅ Resolvida |
| GAP-15 | `workers` | Backend de storage trocado de S3 (nunca provisionado — `S3_ENDPOINT` vazio, sem MinIO no compose) para disco local (`RECORDINGS_PATH`, bind mount `./data/recordings`) — decisão de produto em 2026-06-22 | `workers/audio-upload`, `workers/audio-cleanup` | ✅ Resolvida — pendente validação ponta-a-ponta (Fase 4) |

## Moderadas (impactam qualidade)

| ID | Módulo | Descrição | Spec afetada | Status |
|----|--------|-----------|-------------|--------|
| GAP-03 | `api` | Rate limit in-memory volátil — sem efeito após restart | `api/design.md` | Aberta |
| GAP-04 | `api` | Webhook dispatcher fire-and-forget sem confirmação de entrega | `api/design.md` | Aberta |
| GAP-05 | `domain` | Personas de portaria remota não refletidas no modelo de domínio | `domain.md` | Aberta |
| GAP-06 | `telephony` | Auto-link SIP sem fallback se Redis vazio | `telephony/design.md` | Aberta |

## Cosméticas

| ID | Módulo | Descrição | Spec afetada | Status |
|----|--------|-----------|-------------|--------|
| GAP-07 | `ai` | Contagem de keywords corrigida (13→27) | `ai/requirements.md` | ✅ Resolvida |
| GAP-08 | `c4` | Typo `api_fastagi` → `api_fastapi` | `c4-context.md` | ✅ Resolvida |
| GAP-09 | `stt` | Timeout descrito como hardcoded (é configurável) | `services/stt/design.md` | ✅ Resolvida |
| GAP-10 | `telephony` | Eventos ESL incompletos (faltavam SOFIA events) | `telephony/requirements.md` | ✅ Resolvida |
| GAP-18 | `infra`/`requirements.txt` | `zenith-api-1`/`zenith-api-2` nunca foram buildados com sucesso neste host (10.10.10.11) antes de 2026-07-09 — descoberto ao tentar deployar para validar a feature `007-audio-stream-migration`. `requirements.txt` acumulava pins mortos (`greenswitch==1.1.0`, `redis-streams==0.6.0`, `python-brasilcpf==2.0.0`, todos removidos), um conflito real de dependências (`arq` exige `redis<6`, `langgraph-checkpoint-redis` exige `redis>=6.2.0`, resolvido trocando `RedisSaver` por `MemorySaver`), e `piper-tts==1.2.0` dependente de `piper-phonemize~=1.1.0` (sem wheel disponível) | `requirements.txt`, `src/ai/consensus_graph.py`, `src/services/tts_service.py` | ✅ Resolvida (2026-07-09, feature `008-piper-tts-standalone`) — `piper-tts` atualizado para `1.4.2` (`OHF-Voice/piper1-gpl`, PyPI, sem `piper-phonemize`). `pip install --dry-run -r requirements.txt` resolve 100% sem erros. `zenith-api-1` segue não validado ponta a ponta (build completo da imagem da aplicação), mas todos os bloqueios de dependência conhecidos foram removidos |
