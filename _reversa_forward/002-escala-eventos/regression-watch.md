# Regression Watch: Alta Escala, Isolamento Multitenant e PBX Múltiplos

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`

## Itens de verificação

| ID | Origem | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|--------|---------------------------|---------------------|-------------------|
| W001 | `specs/architecture-guide.md#database` | Database Router deve definir `search_path` para o schema do tenant antes de qualquer query de negócio. | presença | Queries de tenant executando no schema `public` ou schema incorreto. |
| W002 | `src/database/models.py` | Modelos `Call`, `Transcript`, `CallInsight`, `STTMetric` usam `TenantBase` (não `Base`) e são criados por schema. | presença | Modelos sendo criados no schema `public` ao invés de `tenant_*`. |
| W003 | `src/telephony/esl_client.py` | ESL listener deve capturar eventos SOFIA_REGISTER e salvar `zenith:sip:ip_to_extension:<ip>` no Redis com TTL 3600s. | presença | Mapeamento SIP não aparece no Redis após registro de softphone. |
| W004 | `src/telephony/esl_client.py` | CHANNEL_CREATE com destino *88 deve disparar evento de manual linkage no WebSocket. | presença | Chamada *88 não gera evento `manual_linkage_detected`. |
| W005 | `src/api/websockets.py` | Handshake WebSocket deve cruzar IP da conexão com Redis e enviar `session_linked` ou `session_waiting_linkage`. | presença | Widget conecta mas não recebe evento de vínculo. |
| W006 | `src/api/auth.py` | JWT deve conter `tenant_id` e `role` para autorização de tenant_admin. | presença | Token JWT sem tenant_id ou role. |
| W007 | `freeswitch/conf/dialplan/default.xml` | Dialplan deve definir variáveis `zenith_tenant_id`, `zenith_pbx_id`, `zenith_agent_extension` no audio fork. | presença | Audio fork sem metadados de tenant/PBX. |
| W008 | `src/database/database.py` | `create_tenant_schema()` deve criar schema + todas as tabelas TenantBase. | redação | Schema criado mas sem tabelas de negócio. |
| W009 | `src/audio/ingestor.py` | Eventos no Redis Streams CALL_EVENTS devem conter `tenant_id`, `pbx_id`, `agent_extension`. | presença | Eventos de áudio sem metadados de tenant. |

## Histórico de re-extrações

| Data | Re-extração | Veredito | Observações |
|------|-------------|----------|-------------|
| 2026-06-19 | Revisor (revisão completa) | 🟢 8/9 • 🟡 1/9 • 🔴 0/9 | W007 (dialplan vars) não documentado diretamente nas specs, mas presente em flowcharts |

## Resultado: re-extração 2026-06-19

| ID | Veredito | Evidência |
|----|----------|-----------|
| W001 | 🟢 | Database Router search_path documentado em `database/multitenancy/requirements.md` |
| W002 | 🟢 | TenantBase documentado em `database/requirements.md` e `database/multitenancy/requirements.md` |
| W003 | 🟢 | ESL SOFIA_REGISTER documentado em `telephony/esl-integration/requirements.md` (atualizado nesta revisão) |
| W004 | 🟢 | *88 linkage documentado em `telephony/esl-integration/requirements.md` RF-07 |
| W005 | 🟢 | WebSocket handshake/auto-link documentado em `api/websocket/requirements.md` |
| W006 | 🟢 | JWT com tenant_id e role documentado em `api/auth/requirements.md` e `domain.md` |
| W007 | 🟡 | Dialplan vars não documentado nas specs principais, apenas em `flowcharts/telephony-flow.md` |
| W008 | 🟢 | Schema creation documentado em `database/multitenancy/requirements.md` |
| W009 | 🟢 | Metadados em eventos de áudio documentado em `audio/audio-ingestion/requirements.md` |

## Arquivadas

Nenhum item arquivado até o momento.

## Observações

Itens originalmente 🟡 ou 🔴 que não geram watch items com peso de regressão:

- 🟡 Testes de integração (`test_multitenancy.py`) dependem de PostgreSQL rodando — podem falhar em CI sem banco.
- 🟡 Worker S3 (`audio_uploader.py`) requer S3_ENDPOINT configurado — falha graceful com `skipped`.
