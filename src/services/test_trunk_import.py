import pytest
import json


def _importer():
    from src.services.trunk_import import CSVSchemaError, import_trunk_csv, parse_trunk_csv

    return parse_trunk_csv, import_trunk_csv, CSVSchemaError


def test_parse_csv_maps_vitalpbx_fields_and_ignores_virtual_rows():
    # Arrange
    parse_trunk_csv, _, _ = _importer()
    content = (
        "extension,ext_name,technology,device_user,device_password\n"
        "1001,Condominio Demo,pjsip,ata-demo,fixture-secret\n"
        "1002,Virtual,virtual,,fixture-ignored\n"
    ).encode()

    # Act
    result = parse_trunk_csv(content)

    # Assert
    assert len(result.rows) == 1
    assert result.rows[0].auth_username == "ata-demo"
    assert result.rows[0].sip_profile == "internal-7060"
    assert result.ignored == 1


def test_parse_csv_preserves_missing_prefix_as_none():
    # Arrange
    parse_trunk_csv, _, _ = _importer()
    content = (
        "technology,device_user,device_password,condominium\n"
        "pjsip,1020,fixture-secret,Parque Portugal\n"
    ).encode()

    # Act
    result = parse_trunk_csv(content)

    # Assert
    assert result.rows[0].prefix is None
    assert result.rows[0].auth_username == "1020"


def test_parse_csv_rejects_missing_credential_headers_without_echoing_content():
    # Arrange
    parse_trunk_csv, _, CSVSchemaError = _importer()
    canary = "do-not-echo-this"
    content = f"extension,technology\n{canary},sip\n".encode()

    # Act
    with pytest.raises(CSVSchemaError) as error:
        parse_trunk_csv(content)

    # Assert
    assert canary not in str(error.value)


def test_parse_csv_enforces_row_limit():
    # Arrange
    parse_trunk_csv, _, CSVSchemaError = _importer()
    header = "technology,device_user,device_password\n"
    content = (header + "sip,user,secret\n" * 3).encode()

    # Act
    with pytest.raises(CSVSchemaError):
        parse_trunk_csv(content, max_rows=2)

    # Assert
    assert content.count(b"\n") == 4


@pytest.mark.asyncio
async def test_import_csv_dry_run_never_persists_or_encrypts():
    # Arrange
    from unittest.mock import AsyncMock

    _, import_trunk_csv, _ = _importer()
    service = AsyncMock()
    content = b"technology,device_user,device_password\nsip,ata-1,fixture-secret\n"

    # Act
    result = await import_trunk_csv(content, "tenant-a", "pbx-1", dry_run=True, trunk_service=service)

    # Assert
    service.upsert_imported.assert_not_awaited()
    assert result.dry_run is True
    assert result.rows == 1


@pytest.mark.asyncio
async def test_import_csv_repeated_rows_delegate_to_idempotent_upsert():
    # Arrange
    from unittest.mock import AsyncMock

    _, import_trunk_csv, _ = _importer()
    service = AsyncMock()
    service.upsert_imported.side_effect = ["created", "unchanged"]
    content = b"technology,device_user,device_password\nsip,ata-1,fixture-secret\n"

    # Act
    first = await import_trunk_csv(content, "tenant-a", "pbx-1", dry_run=False, trunk_service=service)
    second = await import_trunk_csv(content, "tenant-a", "pbx-1", dry_run=False, trunk_service=service)

    # Assert
    assert first.created == 1
    assert second.unchanged == 1
    assert service.upsert_imported.await_count == 2


@pytest.mark.asyncio
async def test_import_csv_structural_error_happens_before_any_persistence():
    # Arrange
    from unittest.mock import AsyncMock

    _, import_trunk_csv, CSVSchemaError = _importer()
    service = AsyncMock()
    content = b"technology,device_user\nsip,ata-1\n"

    # Act
    with pytest.raises(CSVSchemaError):
        await import_trunk_csv(content, "tenant-a", "pbx-1", dry_run=False, trunk_service=service)

    # Assert
    service.upsert_imported.assert_not_awaited()


def _private_trunk_json(*, local_secret="fixture-secret", remote_secret="fixture-secret"):
    return json.dumps({
        "configuracoes_gerais": {"tecnologia": "PJSIP"},
        "general_configurations": {
            "nome_de_usuario_de_saida": "1020",
            "porta": 7060,
            "segredo_local": local_secret,
            "nome_de_usuario_remoto": "1020",
            "segredo_remoto": remote_secret,
        },
    }).encode()


def test_parse_private_json_maps_7060_without_inventing_prefix():
    # Arrange
    from src.services.trunk_import import parse_trunk_json

    # Act
    row = parse_trunk_json(_private_trunk_json(), condominium_name="Parque Portugal")

    # Assert
    assert row.condominium_name == "Parque Portugal"
    assert row.auth_username == "1020"
    assert row.sip_profile == "internal-7060"
    assert row.prefix is None
    assert "fixture-secret" not in repr(row)


def test_parse_private_json_rejects_secret_mismatch_without_leaking_values():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json

    local = "local-canary-secret"
    remote = "remote-canary-secret"

    # Act
    with pytest.raises(CSVSchemaError) as error:
        parse_trunk_json(
            _private_trunk_json(local_secret=local, remote_secret=remote),
            condominium_name="Parque Portugal",
        )

    # Assert
    assert str(error.value) == "trunk_json_credentials_mismatch"
    assert local not in str(error.value)
    assert remote not in str(error.value)


@pytest.mark.asyncio
async def test_import_private_json_dry_run_never_persists_or_encrypts():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunk_import import import_trunk_json

    service = AsyncMock()

    # Act
    result = await import_trunk_json(
        _private_trunk_json(),
        "tenant-a",
        "pbx-1",
        condominium_name="Parque Portugal",
        condominium_id="condo-1",
        dry_run=True,
        trunk_service=service,
    )

    # Assert
    assert result.dry_run is True
    assert result.rows == 1
    service.upsert_imported.assert_not_awaited()
