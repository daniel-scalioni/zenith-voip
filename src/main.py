from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.config import settings
from src.api.rate_limit import rate_limit_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.database.database import init_db
    await init_db()
    yield


app = FastAPI(
    title="Zenith AI Audio Hub",
    version="1.0.0",
    lifespan=lifespan,
)

app.middleware("http")(rate_limit_middleware)


@app.get("/health")
async def health():
    return {"status": "ok", "instance_id": settings.INSTANCE_ID}


@app.get("/ready")
async def ready():
    return {"status": "ready", "instance_id": settings.INSTANCE_ID}
