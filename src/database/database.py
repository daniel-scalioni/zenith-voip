from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from src.database.models import Base, TenantBase
from src.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_tenant_db(tenant_schema: str) -> AsyncSession:
    async with engine.connect() as conn:
        await conn.execute(text(f"SET search_path TO {tenant_schema}, public"))
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
            # session.commit() só finaliza a transação lógica do ORM; a Connection
            # (aberta via engine.connect(), com autobegin pelo SET search_path) só
            # persiste de verdade com um commit explícito nela. Sem isso, sair do
            # `async with engine.connect()` faz rollback silencioso de tudo.
            await conn.commit()
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_tenant_schema(schema_name: str):
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        await conn.execute(text(f"SET search_path TO {schema_name}"))
        await conn.run_sync(TenantBase.metadata.create_all)


async def run_migrations_for_schema(schema_name: str):
    from alembic.config import Config
    from alembic import command
    import os

    os.environ["SCHEMA_NAME"] = schema_name
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


def tenant_session(tenant_schema: str):
    async def _get():
        async for session in get_tenant_db(tenant_schema):
            yield session
    return _get
