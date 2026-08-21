import logging
import time
import uuid
from fastapi import Request, HTTPException, status
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from src.events.redis_streams import event_bus

logger = logging.getLogger(__name__)

RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60


async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    key = f"zenith:ratelimit:{client_ip}"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    redis = event_bus.redis
    limited = False

    try:
        await redis.zremrangebyscore(key, 0, window_start)
        count = await redis.zcard(key)
        limited = count >= RATE_LIMIT_REQUESTS

        if not limited:
            # Membro precisa ser único no sorted set -- duas requisições podem cair no
            # mesmo timestamp; o score (usado para poda por janela) continua sendo `now`.
            await redis.zadd(key, {f"{now}:{uuid.uuid4()}": now})
            await redis.expire(key, RATE_LIMIT_WINDOW)
    except (RedisConnectionError, RedisTimeoutError) as e:
        # Fail-open só para falha de infra (conexão/timeout): o rate limiter é defesa
        # em profundidade, não a única linha de defesa -- falhar fechado aqui derrubaria
        # toda a API por causa de um blip do Redis, pior que o problema que este fix
        # resolve (GAP-03). Outros RedisError (ex: ResponseError por comando malformado)
        # não são capturados aqui -- propagam como bug real, não somem como "infra
        # indisponível" em silêncio.
        logger.warning("Rate limit check failed (Redis unavailable), allowing request: %s", e)

    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s.",
        )

    response = await call_next(request)
    return response
