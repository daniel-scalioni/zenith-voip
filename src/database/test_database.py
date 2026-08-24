"""Regressão do GAP-32: pool precisa detectar conexão morta antes de reusá-la."""
from src.database.database import engine


def test_engine_pool_has_pre_ping_enabled():
    # Arrange / Act
    pre_ping = engine.pool._pre_ping

    # Assert: sem isso, um worker de vida longa (ex: zenith-smb-sync) com conexão
    # ociosa durante um restart do Postgres (manutenção, failover, recreate de
    # container) recebe "connection is closed" no próximo uso em vez de reconectar
    # sozinho — visto em produção em 2026-08-24 após recriar o container postgres
    # pro fix do GAP-31
    assert pre_ping is True
