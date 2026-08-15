from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    INSTANCE_ID: int = 1
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    REDIS_URL: str = "redis://redis:6379/0"
    DATABASE_URL: str = "postgresql+asyncpg://zenith:zenith@postgres:5432/zenith"

    FREESWITCH_ESL_HOST: str = "172.21.0.1"
    FREESWITCH_ESL_PORT: int = 8021
    FREESWITCH_ESL_PASSWORD: str = "ClueCon"
    TRUNK_CREDENTIAL_KEYS: str = ""
    FREESWITCH_DIRECTORY_BASIC_USERNAME: str = ""
    FREESWITCH_DIRECTORY_BASIC_PASSWORD: str = ""
    FREESWITCH_DIRECTORY_URL: str = "http://127.0.0.1:8001/internal/freeswitch/directory"
    FREESWITCH_DIRECTORY_TIMEOUT_SECONDS: float = Field(default=2.0, gt=0, le=10)
    LEGACY_DIRECTORY_PATH: str = "/run/zenith-directory/extensions.xml"

    AUDIO_STREAM_CALLBACK_HOST: str = "127.0.0.1:8001"

    DEEPGRAM_API_KEY: str = ""
    OLLAMA_URL: str = "http://ollama:11434"

    PIPER_VOICE_PATH: str = "audio/voices/pt_BR-faber-medium.onnx"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    REDIS_STREAM_CALL_EVENTS: str = "call:events"
    REDIS_STREAM_POST_CALL: str = "call:post"
    REDIS_CONSUMER_GROUP: str = "zenith-workers"

    STT_FALLBACK_TIMEOUT_MS: int = 500
    BATCH_INSERT_INTERVAL_SECONDS: int = 5

    AUDIO_RETENTION_DAYS: float = 90
    RECORDINGS_PATH: str = "/data/recordings"
    RECORDING_REQUIRED_CONSUMERS: list[str] = ["smb"]
    RECORDING_MAX_CALL_SECONDS: int = Field(default=300, gt=0)
    RECORDING_MIN_FREE_PERCENT: float = Field(default=20, ge=0, lt=100)
    RECORDING_RESUME_FREE_PERCENT: float = Field(default=30, gt=0, le=100)
    RECORDING_PROCESSING_HEADROOM_BYTES: int = Field(default=134_217_728, ge=0)
    RECORDING_LEASE_TTL_SECONDS: int = Field(default=120, gt=0)
    RECORDING_LEASE_HEARTBEAT_SECONDS: int = Field(default=30, gt=0)
    RECORDING_CLEANUP_ROUND_SECONDS: int = Field(default=900, gt=0)

    SMB_ENABLED: bool = False
    SMB_HOST: str = ""
    SMB_PORT: int = Field(default=445, ge=1, le=65535)
    SMB_IS_DIRECT_TCP: bool = True
    SMB_CLIENT_NAME: str = Field(default="ZENITH", min_length=1, max_length=15)
    SMB_SERVER_NAME: str = Field(default="", max_length=15)
    SMB_DOMAIN: str = ""
    SMB_USE_NTLM_V2: bool = True
    SMB_SIGN_OPTIONS: int = Field(default=2, ge=0, le=2)
    SMB_SHARE: str = ""
    SMB_PATH: str = ""
    SMB_USERNAME: str = ""
    SMB_PASSWORD: str = ""
    SMB_BANDWIDTH_LIMIT_MBS: float = Field(default=5, gt=0)
    SMB_TRANSFER_LOG_PATH: str = "/data/smb_logs/smb_transfer_log.json"
    SMB_SYNC_INTERVAL_MINUTES: int = Field(default=5, ge=1, le=59)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @model_validator(mode="after")
    def validate_smb_configuration(self):
        if self.RECORDING_RESUME_FREE_PERCENT <= self.RECORDING_MIN_FREE_PERCENT:
            raise ValueError("A margem de retomada deve ser maior que a margem mínima")
        if not self.SMB_ENABLED:
            return self
        required = {
            "SMB_HOST": self.SMB_HOST,
            "SMB_SERVER_NAME": self.SMB_SERVER_NAME,
            "SMB_SHARE": self.SMB_SHARE,
            "SMB_USERNAME": self.SMB_USERNAME,
            "SMB_PASSWORD": self.SMB_PASSWORD,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"SMB habilitado sem campos obrigatórios: {', '.join(missing)}")
        if self.SMB_IS_DIRECT_TCP and self.SMB_PORT == 139:
            raise ValueError("Direct TCP não pode usar a porta NetBIOS 139")
        return self


settings = Settings()
