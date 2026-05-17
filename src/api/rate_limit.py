from fastapi import Request, HTTPException, status
import time
from collections import defaultdict

rate_limit_store: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60


async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    history = rate_limit_store[client_ip]
    rate_limit_store[client_ip] = [t for t in history if t > window_start]

    if len(rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s.",
        )

    rate_limit_store[client_ip].append(now)
    response = await call_next(request)
    return response
