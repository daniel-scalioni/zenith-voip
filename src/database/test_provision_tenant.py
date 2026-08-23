"""Contrato do provisionador real de tenant e restore (ADR-011)."""

import importlib.util
import inspect
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(PROJECT_ROOT)) if str(PROJECT_ROOT) not in sys.path else None
from src.database.models import PBX, Tenant, TenantBase


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "zenith_provision_tenant", PROJECT_ROOT / "scripts" / "provision_tenant.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


provision_tenant = _load_script()


class FakeSession:
    def __init__(self, existing=(), fail_at=None):
        self.existing = iter(existing)
        self.fail_at = fail_at
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self): return self
    async def __aexit__(self, *_exc): return None
    async def scalar(self, _statement): return next(self.existing, None)
    def add(self, model): self.added.append(model)
    async def commit(self):
        self.commits += 1
        if self.fail_at == f"commit-{self.commits}":
            raise ConnectionError(self.fail_at)
    async def refresh(self, model):
        if self.fail_at == "refresh": raise ConnectionError("refresh")
        if model.id is None: model.id = uuid.uuid4()
    async def rollback(self): self.rollbacks += 1


def _install_ports(monkeypatch, session, schema_error=None):
    schemas = []
    monkeypatch.setattr(provision_tenant, "async_session_factory", lambda: session)
    async def create_schema(name):
        if schema_error: raise schema_error
        schemas.append(name)
    monkeypatch.setattr(provision_tenant, "create_tenant_schema", create_schema)
    return schemas


def _assert_restore_signature():
    assert {"tenant_id", "pbx_id", "restore"} <= set(
        inspect.signature(provision_tenant.provision).parameters
    )


@pytest.mark.asyncio
async def test_restore_true_preserves_both_explicit_uuids(monkeypatch):
    # Arrange
    _assert_restore_signature()
    tenant_id, pbx_id = uuid.uuid4(), uuid.uuid4()
    session = FakeSession()
    schemas = _install_ports(monkeypatch, session)

    # Act
    await provision_tenant.provision(
        "Restore", "tenant_restore", "PBX", "pbx.invalid", 5060,
        tenant_id=tenant_id, pbx_id=pbx_id, restore=True,
    )

    # Assert
    tenant = next(value for value in session.added if isinstance(value, Tenant))
    pbx = next(value for value in session.added if isinstance(value, PBX))
    assert (tenant.id, pbx.id, pbx.tenant_id) == (tenant_id, pbx_id, tenant_id)
    assert schemas == ["tenant_restore"]


@pytest.mark.asyncio
async def test_normal_flow_generates_ids_and_rejects_explicit_uuid(monkeypatch):
    # Arrange
    _assert_restore_signature()
    session = FakeSession()
    _install_ports(monkeypatch, session)

    # Act
    await provision_tenant.provision("Normal", "tenant_normal", "PBX", "pbx.invalid", 5060)

    # Assert
    tenant = next(value for value in session.added if isinstance(value, Tenant))
    pbx = next(value for value in session.added if isinstance(value, PBX))
    assert isinstance(tenant.id, uuid.UUID) and isinstance(pbx.id, uuid.UUID)
    with pytest.raises(ValueError):
        await provision_tenant.provision(
            "Wrong mode", "tenant_wrong", "PBX", "pbx.invalid", 5060,
            tenant_id=uuid.uuid4(), pbx_id=uuid.uuid4(), restore=False,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("tenant_id,pbx_id", [(uuid.uuid4(), None), (None, uuid.uuid4())])
async def test_restore_rejects_only_one_explicit_uuid(monkeypatch, tenant_id, pbx_id):
    # Arrange
    _assert_restore_signature()
    session = FakeSession()
    _install_ports(monkeypatch, session)

    # Act / Assert
    with pytest.raises(ValueError):
        await provision_tenant.provision(
            "Partial", "tenant_partial", "PBX", "pbx.invalid", 5060,
            tenant_id=tenant_id, pbx_id=pbx_id, restore=True,
        )
    assert session.added == []


@pytest.mark.asyncio
async def test_restore_rejects_uuid_conflict_without_writes(monkeypatch):
    # Arrange
    _assert_restore_signature()
    existing = Tenant(id=uuid.uuid4(), name="Existing", schema_name="tenant_conflict")
    session = FakeSession(existing=(existing,))
    _install_ports(monkeypatch, session)

    # Act / Assert
    with pytest.raises(ValueError, match="UUID|uuid|conflito"):
        await provision_tenant.provision(
            "Conflict", "tenant_conflict", "PBX", "pbx.invalid", 5060,
            tenant_id=uuid.uuid4(), pbx_id=uuid.uuid4(), restore=True,
        )
    assert session.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["commit-1", "refresh", "commit-2", "schema"])
async def test_failure_at_each_boundary_rolls_back_without_success(monkeypatch, failure):
    # Arrange
    _assert_restore_signature()
    session = FakeSession(fail_at=None if failure == "schema" else failure)
    schemas = _install_ports(
        monkeypatch, session,
        schema_error=ConnectionError("schema") if failure == "schema" else None,
    )

    # Act / Assert
    with pytest.raises(ConnectionError):
        await provision_tenant.provision(
            "Failure", "tenant_failure", "PBX", "pbx.invalid", 5060,
            tenant_id=uuid.uuid4(), pbx_id=uuid.uuid4(), restore=True,
        )
    assert session.rollbacks == 1
    assert schemas == []


@pytest.mark.asyncio
@pytest.mark.parametrize("schema", ["public", "tenant_", "tenant_bad-name", "tenant_bad_name"])
async def test_unsafe_schema_is_rejected_before_write(monkeypatch, schema):
    # Arrange
    session = FakeSession()
    _install_ports(monkeypatch, session)

    # Act / Assert
    with pytest.raises(ValueError):
        await provision_tenant.provision("Unsafe", schema, "PBX", "pbx.invalid", 5060)
    assert session.added == []


@pytest.mark.asyncio
async def test_restore_creates_tenant_topology_without_business_tables_in_public(
    isolated_test_database, monkeypatch
):
    # Arrange
    _assert_restore_signature()
    database_url = isolated_test_database.database_url
    tenant_id, pbx_id = uuid.uuid4(), uuid.uuid4()
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT, env=env, check=True, capture_output=True, text=True, timeout=60,
    )
    engine = create_async_engine(database_url)
    monkeypatch.setattr(provision_tenant, "async_session_factory", async_sessionmaker(engine))

    async def create_schema(schema_name):
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            translated = await connection.execution_options(
                schema_translate_map={None: schema_name}
            )
            await translated.run_sync(TenantBase.metadata.create_all)

    monkeypatch.setattr(provision_tenant, "create_tenant_schema", create_schema)

    # Act
    try:
        await provision_tenant.provision(
            "Topology", "tenant_topology", "PBX", "pbx.invalid", 5060,
            tenant_id=tenant_id, pbx_id=pbx_id, restore=True,
        )
        async with engine.connect() as connection:
            rows = await connection.execute(text(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema IN ('public','tenant_topology')"
            ))
            topology = set(rows.tuples())
            tenant_row = (await connection.execute(text(
                "SELECT id FROM public.tenants WHERE schema_name='tenant_topology'"
            ))).one()
            pbx_row = (await connection.execute(text(
                "SELECT id, tenant_id FROM public.pbxs WHERE tenant_id=:tenant_id"
            ), {"tenant_id": tenant_row.id})).one()
    finally:
        await engine.dispose()

    # Assert
    business = {"calls", "transcripts", "call_insights", "stt_metrics"}
    assert {("tenant_topology", table) for table in business} <= topology
    assert not ({("public", table) for table in business} & topology)
    assert tenant_row.id == tenant_id
    assert pbx_row.id == pbx_id
    assert pbx_row.tenant_id == tenant_id


class FailingRealSession:
    """Port de falha sobre AsyncSession real; não simula persistência."""

    def __init__(self, factory, failure):
        self._session = factory()
        self._failure = failure
        self._commits = 0

    async def __aenter__(self):
        await self._session.__aenter__()
        return self

    async def __aexit__(self, *exc):
        return await self._session.__aexit__(*exc)

    def add(self, value):
        return self._session.add(value)

    async def scalar(self, statement):
        return await self._session.scalar(statement)

    async def commit(self):
        self._commits += 1
        if self._failure == f"commit-{self._commits}":
            raise ConnectionError(self._failure)
        await self._session.commit()

    async def refresh(self, value):
        if self._failure == "refresh":
            raise ConnectionError("refresh")
        await self._session.refresh(value)

    async def rollback(self):
        await self._session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["commit-1", "refresh", "commit-2", "schema"])
async def test_real_boundary_failure_leaves_no_tenant_pbx_or_schema(
    isolated_test_database, monkeypatch, failure
):
    # Arrange
    _assert_restore_signature()
    database_url = isolated_test_database.database_url
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT, env=env, check=True, capture_output=True, text=True, timeout=60,
    )
    engine = create_async_engine(database_url)
    real_factory = async_sessionmaker(engine)
    monkeypatch.setattr(
        provision_tenant,
        "async_session_factory",
        lambda: FailingRealSession(real_factory, failure),
    )

    async def create_schema(schema_name):
        if failure == "schema":
            raise ConnectionError("schema")
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    monkeypatch.setattr(provision_tenant, "create_tenant_schema", create_schema)

    # Act
    try:
        with pytest.raises(ConnectionError):
            await provision_tenant.provision(
                "Atomic", "tenant_atomic", "PBX", "pbx.invalid", 5060,
                tenant_id=uuid.uuid4(), pbx_id=uuid.uuid4(), restore=True,
            )
        async with engine.connect() as connection:
            tenant_count = (await connection.execute(text(
                "SELECT count(*) FROM public.tenants WHERE schema_name='tenant_atomic'"
            ))).scalar_one()
            pbx_count = (await connection.execute(text(
                "SELECT count(*) FROM public.pbxs WHERE name='PBX'"
            ))).scalar_one()
            schema_count = (await connection.execute(text(
                "SELECT count(*) FROM information_schema.schemata "
                "WHERE schema_name='tenant_atomic'"
            ))).scalar_one()
    finally:
        await engine.dispose()

    # Assert
    assert (tenant_count, pbx_count, schema_count) == (0, 0, 0)


# --- --sync-vars-xml (GAP-RE-07): opt-in, chama scripts/sync_vars_xml.py::sync ---


class _FakeSyncVarsXmlModule:
    def __init__(self, changed: bool = True):
        self.calls = []
        self._changed = changed

    async def sync(self, schema_name, vars_xml_path, *, check_only):
        self.calls.append((schema_name, vars_xml_path, check_only))
        return self._changed


@pytest.mark.asyncio
async def test_sync_vars_xml_path_none_never_touches_vars_xml(monkeypatch):
    # Arrange
    session = FakeSession()
    _install_ports(monkeypatch, session)
    fake_module = _FakeSyncVarsXmlModule()
    monkeypatch.setattr(provision_tenant, "_load_sync_vars_xml", lambda: fake_module)

    # Act
    await provision_tenant.provision("Normal", "tenant_normal2", "PBX", "pbx.invalid", 5060)

    # Assert
    assert fake_module.calls == []


@pytest.mark.asyncio
async def test_sync_vars_xml_path_set_calls_sync_with_schema_and_path(monkeypatch, tmp_path):
    # Arrange
    session = FakeSession()
    _install_ports(monkeypatch, session)
    fake_module = _FakeSyncVarsXmlModule(changed=True)
    monkeypatch.setattr(provision_tenant, "_load_sync_vars_xml", lambda: fake_module)
    vars_xml_path = tmp_path / "vars.xml"

    # Act
    await provision_tenant.provision(
        "Akom", "tenant_akom2", "PBX", "pbx.invalid", 5060,
        sync_vars_xml_path=vars_xml_path,
    )

    # Assert
    assert fake_module.calls == [("tenant_akom2", vars_xml_path, False)]
