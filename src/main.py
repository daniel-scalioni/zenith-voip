from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager
from src._version import __version__
from src.config import settings
from src.api.rate_limit import rate_limit_middleware
from src.api.routers import pbxs
from src.audio.ingestor import audio_ingestor


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.database.database import init_db
    from src.telephony.esl_client import esl_client

    await init_db()

    # esl_client nunca era conectado em lugar nenhum do código (gap real,
    # descoberto na revisão de segurança de 2026-07-12): CHANNEL_ANSWER/HANGUP
    # nunca eram processados de verdade, então register_stream_metadata()
    # nunca populava audio_ingestor.stream_metadata para chamadas reais.
    # Só a instância 1 conecta ao ESL — evita que fastapi-1 e fastapi-2
    # processem o mesmo evento em duplicidade (create_call_record não é
    # idempotente). _event_loop já reconecta sozinho com backoff de 2s.
    if settings.INSTANCE_ID == 1:
        await esl_client.start_event_listener()

    yield

    if settings.INSTANCE_ID == 1:
        await esl_client.close()


app = FastAPI(
    title="Zenith AI Audio Hub",
    version=__version__,
    lifespan=lifespan,
)

app.middleware("http")(rate_limit_middleware)
app.include_router(pbxs.router)


@app.get("/health")
async def health():
    return {"status": "ok", "instance_id": settings.INSTANCE_ID}


@app.get("/ready")
async def ready():
    return {"status": "ready", "instance_id": settings.INSTANCE_ID}


@app.websocket("/audio-stream/{call_id}")
async def audio_stream(websocket: WebSocket, call_id: str):
    await audio_ingestor.handle_forked_stream(call_id, websocket)
