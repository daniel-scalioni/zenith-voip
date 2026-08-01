"""Fixtures de banco descartável com guard contra o PostgreSQL operacional."""

import os
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

import asyncpg
import pytest

_SAFE_HOST = "zenith-postgres-test"
_SAFE_PORT = 5432
_SAFE_DATABASE = re.compile(r"^zenith_test_[a-z0-9_]+$")


def validate_test_database_url(database_url: str | None) -> str:
    if not database_url:
        raise ValueError("DSN do banco de teste é obrigatório")
    parsed = urlsplit(database_url)
    if parsed.scheme != "postgresql+asyncpg":
        raise ValueError("driver de teste deve ser postgresql+asyncpg")
    if parsed.hostname is None or parsed.hostname.lower() != _SAFE_HOST:
        raise ValueError("host não é o PostgreSQL dedicado de teste")
    if parsed.hostname != parsed.hostname.strip() or "%" in parsed.netloc:
        raise ValueError("hostname ambíguo")
    if parsed.port not in (None, _SAFE_PORT):
        raise ValueError("porta de teste inválida")
    database_name = parsed.path.removeprefix("/")
    if not _SAFE_DATABASE.fullmatch(database_name):
        raise ValueError("nome do database de teste inválido")
    if parsed.query or parsed.fragment:
        raise ValueError("DSN de teste não aceita overrides")
    return database_url


def unique_test_database_name() -> str:
    return f"zenith_test_{uuid.uuid4().hex}"


def unique_test_schema_name() -> str:
    return f"tenant_test_{uuid.uuid4().hex}"


def _replace_database(database_url: str, database_name: str) -> str:
    parsed = urlsplit(database_url)
    return parsed._replace(path=f"/{database_name}").geturl()


@dataclass
class IsolatedTestDatabase:
    database_url: str
    database_name: str
    alembic_head: str = "001_public_baseline"

    async def open_connection(self):
        return await asyncpg.connect(self.database_url.replace("+asyncpg", ""))


class TestDatabaseServer:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def _admin(self):
        return await asyncpg.connect(self.base_url.replace("+asyncpg", ""))

    async def create_database(self, database_name: str) -> str:
        if not _SAFE_DATABASE.fullmatch(database_name):
            raise ValueError("nome de database inseguro")
        connection = await self._admin()
        try:
            await connection.execute(f'CREATE DATABASE "{database_name}"')
        finally:
            await connection.close()
        return database_name

    async def database_exists(self, database_name: str) -> bool:
        connection = await self._admin()
        try:
            return bool(
                await connection.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname=$1", database_name
                )
            )
        finally:
            await connection.close()

    async def delete_database(self, database_name: str) -> None:
        if not _SAFE_DATABASE.fullmatch(database_name):
            raise ValueError("nome de database inseguro")
        connection = await self._admin()
        try:
            await connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=$1 AND pid <> pg_backend_pid()",
                database_name,
            )
            await connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        finally:
            await connection.close()


@asynccontextmanager
async def isolated_test_database(base_url: str):
    validated = validate_test_database_url(base_url)
    server = TestDatabaseServer(validated)
    database_name = unique_test_database_name()
    await server.create_database(database_name)
    resource = IsolatedTestDatabase(
        database_url=_replace_database(validated, database_name),
        database_name=database_name,
    )
    try:
        yield resource
    finally:
        await server.delete_database(database_name)


def _configured_base_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL de teste não configurada")
    return validate_test_database_url(database_url)
