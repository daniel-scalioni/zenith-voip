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
    await init_db()
    yield


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
