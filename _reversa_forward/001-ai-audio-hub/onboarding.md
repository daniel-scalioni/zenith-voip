# Onboarding do Projeto

## Pré-requisitos
- Docker e Docker Compose (v2+)
- Python 3.11+ (para desenvolvimento local sem container)
- Softphone SIP (ex: MicroSIP, Zoiper)
- Chaves de API (Deepgram, OpenAI)

## Subindo o Ambiente Local
1. Copie `.env.example` para `.env` e preencha as variáveis mandatórias:
   - `DEEPGRAM_API_KEY`
   - `OPENAI_API_KEY`
2. Na raiz do projeto, rode:
   ```bash
   docker-compose up -d
   ```
3. O Docker Compose provisionará a stack completa:
   - **FreeSWITCH** (SBC) exposto na porta SIP `5060`.
   - **PostgreSQL** (Database) exposto na `5432`.
   - **Redis** (Message Broker / PubSub) exposto na `6379`.
   - **FastAPI** (Backend Orquestrador) exposto na `8000`.
   - **Celery Worker** (Processamento em background).

## Testando o Fluxo de Ponta a Ponta
1. Registre seu softphone no endereço `localhost:5060` (usuário dummy local).
2. O dialplan de desenvolvimento roteará sua chamada simulando um loopback ou eco.
3. Fale ao microfone.
4. Acompanhe os logs do FreeSWITCH para ver o áudio sendo forkado para o backend via WebSocket/gRPC:
   ```bash
   docker-compose logs -f freeswitch
   ```
5. Acompanhe os logs do Celery para ver a extração de sentimento operando no Pós-chamada:
   ```bash
   docker-compose logs -f celery_worker
   ```
