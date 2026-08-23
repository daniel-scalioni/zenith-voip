"""Contrato de scripts/sync_vars_xml.py (GAP-RE-07)."""

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(PROJECT_ROOT)) if str(PROJECT_ROOT) not in sys.path else None


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "zenith_sync_vars_xml", PROJECT_ROOT / "scripts" / "sync_vars_xml.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sync_vars_xml = _load_script()

SAMPLE_VARS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<include>
  <X-PRE-PROCESS cmd="set" data="local_ip_v4=auto"/>
  <X-PRE-PROCESS cmd="set" data="domain=zenith.local"/>
  <X-PRE-PROCESS cmd="set" data="pbx_host=sip.maisalerta.tecnorise.com"/>

  <X-PRE-PROCESS cmd="set" data="tenant_id=akom"/>
  <X-PRE-PROCESS cmd="set" data="pbx_id=c5bf3191-75b4-4a45-b5e1-c9b7942f8176"/>

  <X-PRE-PROCESS cmd="set" data="global_codec_prefs=OPUS,G722,PCMU,PCMA"/>
</include>
"""


class FakeScalarResult:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return self._items


class FakeSession:
    def __init__(self, tenant=None, pbxs=()):
        self.tenant = tenant
        self.pbxs = list(pbxs)

    async def scalar(self, _stmt):
        return self.tenant

    async def scalars(self, _stmt):
        return FakeScalarResult(self.pbxs)


class FakeTenant:
    def __init__(self, id_, schema_name):
        self.id = id_
        self.schema_name = schema_name


class FakePBX:
    def __init__(self, id_, tenant_id):
        self.id = id_
        self.tenant_id = tenant_id


# --- render_updated_vars_xml (função pura) ---


def test_render_updated_vars_xml_replaces_only_the_two_target_lines():
    # Arrange / Act
    result = sync_vars_xml.render_updated_vars_xml(SAMPLE_VARS_XML, "novoslug", "1111-2222")

    # Assert
    assert 'data="tenant_id=novoslug"' in result
    assert 'data="pbx_id=1111-2222"' in result
    assert 'data="tenant_id=akom"' not in result
    assert 'data="pbx_id=c5bf3191-75b4-4a45-b5e1-c9b7942f8176"' not in result


def test_render_updated_vars_xml_preserves_everything_else_byte_for_byte():
    # Arrange / Act
    result = sync_vars_xml.render_updated_vars_xml(SAMPLE_VARS_XML, "novoslug", "1111-2222")

    # Assert
    assert 'data="domain=zenith.local"' in result
    assert 'data="pbx_host=sip.maisalerta.tecnorise.com"' in result
    assert 'data="global_codec_prefs=OPUS,G722,PCMU,PCMA"' in result
    assert result.count("\n") == SAMPLE_VARS_XML.count("\n")


def test_render_updated_vars_xml_raises_when_tenant_id_line_missing():
    # Arrange
    content = SAMPLE_VARS_XML.replace(
        '  <X-PRE-PROCESS cmd="set" data="tenant_id=akom"/>\n', ""
    )

    # Act / Assert
    with pytest.raises(ValueError, match="tenant_id"):
        sync_vars_xml.render_updated_vars_xml(content, "novoslug", "1111-2222")


def test_render_updated_vars_xml_raises_when_pbx_id_line_missing():
    # Arrange
    content = SAMPLE_VARS_XML.replace(
        '  <X-PRE-PROCESS cmd="set" data="pbx_id=c5bf3191-75b4-4a45-b5e1-c9b7942f8176"/>\n', ""
    )

    # Act / Assert
    with pytest.raises(ValueError, match="pbx_id"):
        sync_vars_xml.render_updated_vars_xml(content, "novoslug", "1111-2222")


# --- extract_current_values (função pura) ---


def test_extract_current_values_reads_existing_tenant_and_pbx():
    # Arrange / Act
    tenant_slug, pbx_id = sync_vars_xml.extract_current_values(SAMPLE_VARS_XML)

    # Assert
    assert tenant_slug == "akom"
    assert pbx_id == "c5bf3191-75b4-4a45-b5e1-c9b7942f8176"


def test_extract_current_values_returns_none_for_missing_lines():
    # Arrange
    content = "<include></include>"

    # Act
    tenant_slug, pbx_id = sync_vars_xml.extract_current_values(content)

    # Assert
    assert tenant_slug is None
    assert pbx_id is None


# --- resolve_tenant_pbx (async, contra sessão fake) ---


@pytest.mark.asyncio
async def test_resolve_tenant_pbx_returns_slug_and_pbx_id():
    # Arrange
    tenant_id = uuid.uuid4()
    pbx_id = uuid.uuid4()
    session = FakeSession(
        tenant=FakeTenant(tenant_id, "tenant_akom"),
        pbxs=[FakePBX(pbx_id, tenant_id)],
    )

    # Act
    slug, resolved_pbx_id = await sync_vars_xml.resolve_tenant_pbx(session, "tenant_akom")

    # Assert
    assert slug == "akom"
    assert resolved_pbx_id == str(pbx_id)


@pytest.mark.asyncio
async def test_resolve_tenant_pbx_raises_when_tenant_not_found():
    # Arrange
    session = FakeSession(tenant=None)

    # Act / Assert
    with pytest.raises(ValueError, match="não encontrado"):
        await sync_vars_xml.resolve_tenant_pbx(session, "tenant_inexistente")


@pytest.mark.asyncio
async def test_resolve_tenant_pbx_raises_when_tenant_has_no_pbx():
    # Arrange
    tenant_id = uuid.uuid4()
    session = FakeSession(tenant=FakeTenant(tenant_id, "tenant_akom"), pbxs=[])

    # Act / Assert
    with pytest.raises(ValueError, match=r"0 PBX"):
        await sync_vars_xml.resolve_tenant_pbx(session, "tenant_akom")


@pytest.mark.asyncio
async def test_resolve_tenant_pbx_raises_when_tenant_has_more_than_one_pbx():
    # Arrange
    tenant_id = uuid.uuid4()
    session = FakeSession(
        tenant=FakeTenant(tenant_id, "tenant_akom"),
        pbxs=[FakePBX(uuid.uuid4(), tenant_id), FakePBX(uuid.uuid4(), tenant_id)],
    )

    # Act / Assert
    with pytest.raises(ValueError, match=r"2 PBX"):
        await sync_vars_xml.resolve_tenant_pbx(session, "tenant_akom")


# --- write_atomic ---


def test_write_atomic_writes_full_content(tmp_path):
    # Arrange
    output = tmp_path / "vars.xml"

    # Act
    sync_vars_xml.write_atomic(output, "conteudo novo")

    # Assert
    assert output.read_text(encoding="utf-8") == "conteudo novo"


def test_write_atomic_leaves_no_temp_file_behind(tmp_path):
    # Arrange
    output = tmp_path / "vars.xml"

    # Act
    sync_vars_xml.write_atomic(output, "conteudo")

    # Assert
    leftovers = [p for p in tmp_path.iterdir() if p.name != "vars.xml"]
    assert leftovers == []


def test_write_atomic_preserves_existing_file_mode(tmp_path):
    # Arrange
    output = tmp_path / "vars.xml"
    output.write_text("conteudo antigo", encoding="utf-8")
    output.chmod(0o644)

    # Act
    sync_vars_xml.write_atomic(output, "conteudo novo")

    # Assert
    assert output.stat().st_mode & 0o777 == 0o644


def test_write_atomic_defaults_to_0644_for_new_file(tmp_path):
    # Arrange
    output = tmp_path / "vars.xml"

    # Act
    sync_vars_xml.write_atomic(output, "conteudo")

    # Assert
    assert output.stat().st_mode & 0o777 == 0o644


# --- sync() fim a fim, contra arquivo real em tmp_path e sessão fake ---


@pytest.mark.asyncio
async def test_sync_writes_file_when_diverged(tmp_path, monkeypatch):
    # Arrange
    vars_xml = tmp_path / "vars.xml"
    vars_xml.write_text(SAMPLE_VARS_XML, encoding="utf-8")
    pbx_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    fake_session = FakeSession(
        tenant=FakeTenant(tenant_id, "tenant_akom"), pbxs=[FakePBX(pbx_id, tenant_id)]
    )
    monkeypatch.setattr(
        sync_vars_xml, "async_session_factory", lambda: _AsyncCtx(fake_session)
    )

    # Act
    changed = await sync_vars_xml.sync("tenant_akom", vars_xml, check_only=False)

    # Assert
    assert changed is True
    assert f'data="pbx_id={pbx_id}"' in vars_xml.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_sync_check_only_does_not_write(tmp_path, monkeypatch):
    # Arrange
    vars_xml = tmp_path / "vars.xml"
    vars_xml.write_text(SAMPLE_VARS_XML, encoding="utf-8")
    pbx_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    fake_session = FakeSession(
        tenant=FakeTenant(tenant_id, "tenant_akom"), pbxs=[FakePBX(pbx_id, tenant_id)]
    )
    monkeypatch.setattr(
        sync_vars_xml, "async_session_factory", lambda: _AsyncCtx(fake_session)
    )
    original = vars_xml.read_text(encoding="utf-8")

    # Act
    changed = await sync_vars_xml.sync("tenant_akom", vars_xml, check_only=True)

    # Assert
    assert changed is True
    assert vars_xml.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_sync_returns_false_when_already_matching(tmp_path, monkeypatch):
    # Arrange
    vars_xml = tmp_path / "vars.xml"
    vars_xml.write_text(SAMPLE_VARS_XML, encoding="utf-8")
    tenant_id = uuid.uuid4()
    pbx_id = uuid.UUID("c5bf3191-75b4-4a45-b5e1-c9b7942f8176")
    fake_session = FakeSession(
        tenant=FakeTenant(tenant_id, "tenant_akom"), pbxs=[FakePBX(pbx_id, tenant_id)]
    )
    monkeypatch.setattr(
        sync_vars_xml, "async_session_factory", lambda: _AsyncCtx(fake_session)
    )
    original = vars_xml.read_text(encoding="utf-8")

    # Act
    changed = await sync_vars_xml.sync("tenant_akom", vars_xml, check_only=False)

    # Assert
    assert changed is False
    assert vars_xml.read_text(encoding="utf-8") == original


# --- main() (CLI) ---


def _stub_sync(return_value):
    async def _fake_sync(*_a, **_k):
        return return_value
    return _fake_sync


def test_main_check_mode_exits_1_when_diverged(monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(sync_vars_xml, "sync", _stub_sync(True))
    monkeypatch.setattr(sys, "argv", ["sync_vars_xml.py", "--schema", "tenant_akom", "--check"])

    # Act / Assert
    with pytest.raises(SystemExit) as excinfo:
        sync_vars_xml.main()
    assert excinfo.value.code == 1
    assert "DIVERGENTE" in capsys.readouterr().out


def test_main_check_mode_prints_ok_when_matching(monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(sync_vars_xml, "sync", _stub_sync(False))
    monkeypatch.setattr(sys, "argv", ["sync_vars_xml.py", "--schema", "tenant_akom", "--check"])

    # Act
    sync_vars_xml.main()

    # Assert
    assert "OK" in capsys.readouterr().out


def test_main_write_mode_reports_when_changed(monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(sync_vars_xml, "sync", _stub_sync(True))
    monkeypatch.setattr(sys, "argv", ["sync_vars_xml.py", "--schema", "tenant_akom"])

    # Act
    sync_vars_xml.main()

    # Assert
    assert "atualizado" in capsys.readouterr().out


def test_main_write_mode_reports_when_already_synced(monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(sync_vars_xml, "sync", _stub_sync(False))
    monkeypatch.setattr(sys, "argv", ["sync_vars_xml.py", "--schema", "tenant_akom"])

    # Act
    sync_vars_xml.main()

    # Assert
    assert "já estava sincronizado" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_sync_check_only_reports_diverged_when_target_lines_missing(tmp_path, monkeypatch):
    # Arrange: vars.xml sem a linha tenant_id — extract_current_values devolve None,
    # que já difere de qualquer slug real, então check reporta divergência sem
    # precisar tentar (e falhar) reescrever.
    vars_xml = tmp_path / "vars.xml"
    vars_xml.write_text("<include></include>", encoding="utf-8")
    tenant_id = uuid.uuid4()
    pbx_id = uuid.uuid4()
    fake_session = FakeSession(
        tenant=FakeTenant(tenant_id, "tenant_akom"), pbxs=[FakePBX(pbx_id, tenant_id)]
    )
    monkeypatch.setattr(
        sync_vars_xml, "async_session_factory", lambda: _AsyncCtx(fake_session)
    )

    # Act
    changed = await sync_vars_xml.sync("tenant_akom", vars_xml, check_only=True)

    # Assert
    assert changed is True
    assert vars_xml.read_text(encoding="utf-8") == "<include></include>"


@pytest.mark.asyncio
async def test_sync_write_mode_raises_when_target_lines_missing_instead_of_silently_failing(
    tmp_path, monkeypatch
):
    # Arrange: mesma situação, mas em modo escrita — o operador seguiu a dica de
    # "DIVERGENTE" do --check e rodou sem --check; precisa de um erro claro, não
    # de um arquivo intocado sem explicação.
    vars_xml = tmp_path / "vars.xml"
    vars_xml.write_text("<include></include>", encoding="utf-8")
    tenant_id = uuid.uuid4()
    pbx_id = uuid.uuid4()
    fake_session = FakeSession(
        tenant=FakeTenant(tenant_id, "tenant_akom"), pbxs=[FakePBX(pbx_id, tenant_id)]
    )
    monkeypatch.setattr(
        sync_vars_xml, "async_session_factory", lambda: _AsyncCtx(fake_session)
    )

    # Act / Assert
    with pytest.raises(ValueError, match="tenant_id"):
        await sync_vars_xml.sync("tenant_akom", vars_xml, check_only=False)
    assert vars_xml.read_text(encoding="utf-8") == "<include></include>"


class _AsyncCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_exc):
        return False
