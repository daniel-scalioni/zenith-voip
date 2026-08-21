"""Fixtures para os testes de ``src/api/`` e ``src/api/routers/`` que sobem o app
real via ``TestClient`` (ex: ``test_trunks.py``, ``test_freeswitch_directory.py``)."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _stub_rate_limit_redis(monkeypatch):
    # rate_limit_middleware roda em toda requisição que passa pelo TestClient(app) e
    # usa event_bus.redis (o singleton compartilhado por esl_client.py/websockets.py/
    # redis_streams.py, não um cliente local ao rate_limit.py). Sem mock, cada requisição
    # tenta conectar no Redis real -- inexistente neste ambiente de testes. O fail-open
    # do middleware evita quebrar o teste, mas cada uma paga o retry/timeout de conexão
    # do redis-py (segundos), deixando essa fatia da suíte lenta sem necessidade.
    from src.api import rate_limit

    redis = AsyncMock()
    redis.zremrangebyscore = AsyncMock(return_value=0)
    redis.zcard = AsyncMock(return_value=0)
    redis.zadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    monkeypatch.setattr(rate_limit.event_bus, "redis", redis)
    yield redis
