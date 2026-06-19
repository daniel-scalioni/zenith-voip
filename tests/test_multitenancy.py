import pytest
from sqlalchemy import text
from src.database.database import engine, create_tenant_schema, get_tenant_db
from src.database.models import Tenant, PBX
from src.config import settings


@pytest.mark.asyncio
async def test_create_tenant_schema():
    schema_name = "tenant_test_schema"
    await create_tenant_schema(schema_name)

    async with engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{schema_name}'")
        )
        assert result.scalar() == schema_name


@pytest.mark.asyncio
async def test_tenant_schema_creates_tables():
    schema_name = "tenant_test_tables"
    await create_tenant_schema(schema_name)

    async with engine.connect() as conn:
        await conn.execute(text(f"SET search_path TO {schema_name}"))
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"),
            {"s": schema_name},
        )
        tables = {row[0] for row in result}
        assert "calls" in tables
        assert "transcripts" in tables
        assert "call_insights" in tables
        assert "stt_metrics" in tables


@pytest.mark.asyncio
async def test_public_tenants_table():
    async with engine.connect() as conn:
        await conn.execute(text("SET search_path TO public"))
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = {row[0] for row in result}
        assert "tenants" in tables
        assert "pbxs" in tables


@pytest.mark.asyncio
async def test_tenant_db_isolation():
    schema_a = "tenant_iso_a"
    schema_b = "tenant_iso_b"
    await create_tenant_schema(schema_a)
    await create_tenant_schema(schema_b)

    async with engine.connect() as conn:
        await conn.execute(text(f"SET search_path TO {schema_a}"))
        await conn.execute(
            text("INSERT INTO calls (id, call_id, direction, status) VALUES (gen_random_uuid(), 'call-a-001', 'inbound', 'in_progress')")
        )

        await conn.execute(text(f"SET search_path TO {schema_b}"))
        result_b = await conn.execute(
            text("SELECT COUNT(*) FROM calls")
        )
        assert result_b.scalar() == 0

        await conn.execute(text(f"SET search_path TO {schema_a}"))
        result_a = await conn.execute(
            text("SELECT COUNT(*) FROM calls")
        )
        assert result_a.scalar() == 1
