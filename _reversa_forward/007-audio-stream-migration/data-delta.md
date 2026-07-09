# Data Delta: Migração de mod_audio_fork para mod_audio_stream

> Identificador: `007-audio-stream-migration`
> Data: `2026-07-08`

## 1. Resumo

Não há alteração em modelo de dados de aplicação (banco de dados, entidades SQLAlchemy, schema multi-tenant). A mudança é inteiramente em configuração de infraestrutura FreeSWITCH e no formato de invocação do streaming de áudio — não no dado de negócio persistido.

## 2. Estruturas de configuração afetadas

| Estrutura | Antes | Depois |
|-----------|-------|--------|
| `freeswitch/Dockerfile` | Builder compila `mod_audio_fork` a partir de `drachtio-freeswitch-modules` (repo inexistente) | Builder compila `mod_audio_stream` a partir de `amigniter/mod_audio_stream`, com libs `libevent-*` copiadas explicitamente para o stage final |
| `freeswitch/conf/autoload_configs/modules.conf.xml` | `mod_audio_fork` comentado/ausente (nunca chegou a carregar em produção) | `mod_audio_stream` carregado |
| `freeswitch/conf/dialplan/default.xml` (extensão `zenith_audio_fork`) | `uuid_audio_fork ${uuid} start ws://zenith-api-1:8000/audio-stream stereo 8000 {...}` | `uuid_audio_stream ${uuid} start ws://zenith-api-1:8000/audio-stream stereo 8k {...}` |
| Artefatos de build vendorizados | Nenhum — dependia sempre do repositório SignalWire no momento do build | `.deb` de `libfreeswitch1`/`libfreeswitch-dev` guardados localmente (fora do git), reduzindo a dependência de o repositório estar sempre disponível |

## 3. Payload de áudio (WebSocket)

| Aspecto | `mod_audio_fork` (antes) | `mod_audio_stream` (depois, premissa a validar) |
|---------|--------------------------|--------------------------------------------------|
| Formato | PCM16, estéreo, intercalado por canal | PCM16, estéreo, intercalado por canal (mesma convenção, conforme investigação do código-fonte) |
| Sample rate | 8000 Hz | 8000 Hz (`8k`, sem mudança) |
| Consumidor | `src/audio/ingestor.py::AudioIngestor.handle_forked_stream` / `_split_stereo_frame` | Mesmo consumidor, sem mudança de código prevista — validação obrigatória com chamada real |

## 4. Migração necessária

Nenhuma migração de banco de dados (`alembic`). A "migração" é operacional: rebuild da imagem FreeSWITCH em produção e restart do container, seguido de teste real de chamada para validar o payload.
