# Lacunas Identificadas — zenith-voip

> Gerado pelo Revisor em 2026-06-19
> Categorizadas por severidade

---

## Críticas (bloqueiam reimplementação)

| ID | Módulo | Descrição | Spec afetada | Status |
|----|--------|-----------|-------------|--------|
| GAP-01 | `audio` | `_detect_channel()` é stub — canal RX nunca detectado. Investigação (2026-06-19) mostrou que o protocolo real (`mod_audio_fork` stereo) intercala os dois canais no mesmo frame PCM16 — corrigido para de-interleaving em `src/audio/ingestor.py`. Convenção de qual canal é tx/rx ainda não validada contra FreeSWITCH real (🟡, ver `audio/design.md`) | `audio/requirements.md` | Parcialmente resolvida |
| GAP-02 | `workers` | `analyze_sentiment()` e `audit_procedure()` são stubs | `workers/requirements.md` | Aberta |

| GAP-11 | `infra` | Imagem `safarov/freeswitch:1.10.12` usada em `docker-compose.app.yml` **não contém `mod_audio_fork` compilado** (verificado em 2026-06-22 via `find` na imagem) — a gravação via fork de áudio não funciona nessa imagem sem build customizado do módulo (`drachtio-freeswitch-modules`) | `infra/deployment` | Em resolução — `freeswitch/Dockerfile` criado, pendente validação contra build real (requer Docker + token SignalWire) |
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
