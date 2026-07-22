# Data Delta: Invocação de comandos de API do FreeSWITCH via ESL client

> Identificador: `009-api-invocation-via-esl-client`
> Data: `2026-07-14`

## Resumo

Nenhuma mudança em modelo de dados (PostgreSQL, Redis) ou em schema de mensageria (Redis Streams).
A feature altera apenas fluxo de execução (onde um comando ESL é disparado) e configuração
(`src/config.py`, `vars.xml`). Este documento existe por completude do template do ciclo forward,
sem conteúdo de diff de dados a registrar.

## Configuração (fora do modelo de dados, mas fora de código também)

| Item | De | Para |
|------|-----|------|
| `vars.xml#zenith_api_host` | `127.0.0.1:8001` (variável de dialplan, consumida só pela action removida) | removida |
| `vars.xml#audio_fork_dest` (derivada de `zenith_api_host`) | `ws://127.0.0.1:8001/audio-stream/${uuid}` (variável de dialplan, nunca lida por nenhuma Application) | removida |
| `src/config.py#AUDIO_STREAM_CALLBACK_HOST` | inexistente | nova chave, default `"127.0.0.1:8001"`, sobrescrevível via variável de ambiente |

Nenhuma migração Alembic necessária.
