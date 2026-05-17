from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    INSTANCE_ID: int = 1
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    REDIS_URL: str = "redis://redis:6379/0"
    DATABASE_URL: str = "postgresql+asyncpg://zenith:zenith@postgres:5432/zenith"

    FREESWITCH_ESL_HOST: str = "172.20.0.1"
    FREESWITCH_ESL_PORT: int = 8021
    FREESWITCH_ESL_PASSWORD: str = "ClueCon"

    DEEPGRAM_API_KEY: str = ""
    OLLAMA_URL: str = "http://ollama:11434"

    PIPER_TTS_URL: str = "http://piper-tts:5000"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    REDIS_STREAM_CALL_EVENTS: str = "call:events"
    REDIS_STREAM_POST_CALL: str = "call:post"
    REDIS_CONSUMER_GROUP: str = "zenith-workers"

    STT_FALLBACK_TIMEOUT_MS: int = 500
    BATCH_INSERT_INTERVAL_SECONDS: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
