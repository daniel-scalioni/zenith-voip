# Interface: WebSocket de Streaming de Áudio (FreeSWITCH → Zenith)

> Identificador: `007-audio-stream-migration`
> Tipo: WebSocket (interno, FreeSWITCH → FastAPI)

## Antes (mod_audio_fork)

- Comando de ativação (dialplan): `uuid_audio_fork ${uuid} start ws://zenith-api-1:8000/audio-stream stereo 8000 {"call_id":"${uuid}"}`
- Endpoint: `ws://zenith-api-1:8000/audio-stream` (consumido por `src/audio/ingestor.py::AudioIngestor.handle_forked_stream`)
- Payload: frames binários PCM16, estéreo, intercalado (`tx`/`rx` alternados por sample)
- Metadata: JSON `{"call_id": "<uuid>"}` enviado antes do início do streaming

## Depois (mod_audio_stream)

- Comando de ativação (dialplan): `uuid_audio_stream ${uuid} start ws://zenith-api-1:8000/audio-stream stereo 8k {"call_id":"${uuid}"}`
- Endpoint: mesmo — `ws://zenith-api-1:8000/audio-stream`, sem mudança de rota/contrato HTTP
- Payload esperado: frames binários PCM16, estéreo, intercalado — **premissa a validar com teste real** (ver `roadmap.md#Premissas`)
- Metadata: mesmo formato JSON de `call_id`, suportado nativamente pelo parâmetro `metadata` de `uuid_audio_stream`

## Erros e observabilidade

`mod_audio_stream` gera eventos ESL adicionais que `mod_audio_fork` não gerava:
- `mod_audio_stream::connect` — conexão WebSocket estabelecida
- `mod_audio_stream::disconnect` — conexão encerrada (inclui código/motivo)
- `mod_audio_stream::error` — erro de conexão (códigos de 1 a 11, ver `investigation.md`)

Esses eventos não são consumidos por `src/telephony/esl_client.py` hoje — ficam disponíveis para observabilidade futura, mas não são obrigatórios para esta feature funcionar (fora de escopo do RF atual).

## Idempotência e timeouts

- Sem mudança: o streaming é por sessão de chamada (`uuid`), não há reentrega ou at-least-once — se a conexão WebSocket cair, o áudio daquele trecho é perdido (mesmo comportamento de antes com `mod_audio_fork`).
- `STREAM_HEART_BEAT` (variável de canal do `mod_audio_stream`) pode ser configurado para manter a conexão viva atrás de load balancers — não usado nesta feature (sem load balancer entre FreeSWITCH e `zenith-api-1` hoje).
