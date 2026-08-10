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


def test_parse_csv_rejects_content_exceeding_size_limit():
    # Arrange
    parse_trunk_csv, _, CSVSchemaError = _importer()
    content = b"technology,device_user,device_password\nsip,ata-1,fixture-secret\n"

    # Act
    with pytest.raises(CSVSchemaError, match="csv_too_large"):
        parse_trunk_csv(content, max_bytes=10)


def test_parse_csv_rejects_undecodable_content():
    # Arrange
    parse_trunk_csv, _, CSVSchemaError = _importer()
    content = b"\xff\xfe\x00\x81technology,device_user,device_password"

    # Act
    with pytest.raises(CSVSchemaError, match="csv_encoding_invalid"):
        parse_trunk_csv(content)


def test_parse_csv_ignores_unrecognized_technology_without_erroring():
    # Arrange
    parse_trunk_csv, _, _ = _importer()
    content = (
        "technology,device_user,device_password\n"
        "analog,ata-1,fixture-secret\n"
    ).encode()

    # Act
    result = parse_trunk_csv(content)

    # Assert
    assert result.rows == []
    assert result.ignored == 1


def test_parse_csv_rejects_row_missing_username_or_password():
    # Arrange
    parse_trunk_csv, _, CSVSchemaError = _importer()
    content = "technology,device_user,device_password\nsip,,fixture-secret\n".encode()

    # Act
    with pytest.raises(CSVSchemaError, match="csv_row_invalid"):
        parse_trunk_csv(content)


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
async def test_import_csv_counts_updated_outcome():
    # Arrange
    from unittest.mock import AsyncMock

    _, import_trunk_csv, _ = _importer()
    service = AsyncMock()
    service.upsert_imported.return_value = "updated"
    content = b"technology,device_user,device_password\nsip,ata-1,fixture-secret\n"

    # Act
    result = await import_trunk_csv(content, "tenant-a", "pbx-1", dry_run=False, trunk_service=service)

    # Assert
    assert result.updated == 1


@pytest.mark.asyncio
async def test_import_csv_collects_row_errors_without_aborting_batch():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunks import DuplicateIdentityError

    _, import_trunk_csv, _ = _importer()
    service = AsyncMock()
    service.upsert_imported.side_effect = [
        "created",
        DuplicateIdentityError("duplicate_auth_identity"),
        "created",
    ]
    content = (
        "technology,device_user,device_password\n"
        "sip,ata-1,fixture-secret\n"
        "sip,ata-2,fixture-secret\n"
        "sip,ata-3,fixture-secret\n"
    ).encode()

    # Act
    result = await import_trunk_csv(content, "tenant-a", "pbx-1", dry_run=False, trunk_service=service)

    # Assert
    assert result.created == 2
    assert result.rejected == 1
    assert result.errors == [{"line": 3, "code": "duplicate_auth_identity", "field": "auth_username"}]
    assert service.upsert_imported.await_count == 3


@pytest.mark.asyncio
async def test_import_csv_collects_scope_and_value_errors_per_row():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunks import ScopeValidationError

    _, import_trunk_csv, _ = _importer()
    service = AsyncMock()
    service.upsert_imported.side_effect = [
        ScopeValidationError("condominium_not_found"),
        ValueError("invalid_prefix"),
    ]
    content = (
        "technology,device_user,device_password\n"
        "sip,ata-1,fixture-secret\n"
        "sip,ata-2,fixture-secret\n"
    ).encode()

    # Act
    result = await import_trunk_csv(content, "tenant-a", "pbx-1", dry_run=False, trunk_service=service)

    # Assert
    assert result.rejected == 2
    assert result.created == 0
    assert [item["code"] for item in result.errors] == ["condominium_not_found", "invalid_prefix"]
    assert [item["line"] for item in result.errors] == [2, 3]


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


def test_parse_private_json_rejects_oversized_content():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_too_large"):
        parse_trunk_json(_private_trunk_json(), condominium_name="Parque Portugal", max_bytes=10)


def test_parse_private_json_rejects_invalid_json():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_invalid"):
        parse_trunk_json(b"{not valid json", condominium_name="Parque Portugal")


def test_parse_private_json_rejects_empty_condominium_name():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_schema_invalid"):
        parse_trunk_json(_private_trunk_json(), condominium_name="   ")


def test_parse_private_json_rejects_missing_configuration_sections():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json

    content = json.dumps({"configuracoes_gerais": {"tecnologia": "PJSIP"}}).encode()

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_schema_invalid"):
        parse_trunk_json(content, condominium_name="Parque Portugal")


def test_normalize_trunk_entry_rejects_non_numeric_port():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json

    content = _private_trunk_json()
    document = json.loads(content)
    document["general_configurations"]["porta"] = "nao-numerico"

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_sip_configuration_invalid"):
        parse_trunk_json(json.dumps(document).encode(), condominium_name="Parque Portugal")


def test_normalize_trunk_entry_rejects_missing_remote_username():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json

    content = _private_trunk_json()
    document = json.loads(content)
    document["general_configurations"]["nome_de_usuario_remoto"] = ""

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_username_missing"):
        parse_trunk_json(json.dumps(document).encode(), condominium_name="Parque Portugal")


def test_normalize_trunk_entry_rejects_missing_remote_secret():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json

    content = _private_trunk_json()
    document = json.loads(content)
    document["general_configurations"]["segredo_remoto"] = ""

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_secret_missing"):
        parse_trunk_json(json.dumps(document).encode(), condominium_name="Parque Portugal")


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


@pytest.mark.asyncio
async def test_import_private_json_requires_condominium_id_before_persisting():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunk_import import CSVSchemaError, import_trunk_json

    service = AsyncMock()

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_condominium_missing"):
        await import_trunk_json(
            _private_trunk_json(), "tenant-a", "pbx-1",
            condominium_name="Parque Portugal", condominium_id=None,
            dry_run=False, trunk_service=service,
        )

    # Assert
    service.upsert_imported.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_private_json_persists_created_trunk():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunk_import import import_trunk_json

    service = AsyncMock()
    service.upsert_imported.return_value = "created"

    # Act
    result = await import_trunk_json(
        _private_trunk_json(), "tenant-a", "pbx-1",
        condominium_name="Parque Portugal", condominium_id="condo-1",
        dry_run=False, trunk_service=service,
    )

    # Assert
    assert result.created == 1
    persisted_row = service.upsert_imported.await_args.kwargs["row"]
    assert persisted_row.condominium_id == "condo-1"


@pytest.mark.asyncio
async def test_import_private_json_counts_updated_and_unchanged_outcomes():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunk_import import import_trunk_json

    for outcome, field in (("updated", "updated"), ("unchanged", "unchanged")):
        service = AsyncMock()
        service.upsert_imported.return_value = outcome

        # Act
        result = await import_trunk_json(
            _private_trunk_json(), "tenant-a", "pbx-1",
            condominium_name="Parque Portugal", condominium_id="condo-1",
            dry_run=False, trunk_service=service,
        )

        # Assert
        assert getattr(result, field) == 1


def _batch_trunk_entry(
    numero="1020",
    descricao="1020 - Parque Portugal",
    tecnologia="PJSIP",
    porta=7060,
    local_secret="fixture-secret",
    remote_secret="fixture-secret",
    remote_username=None,
):
    return {
        "numero": numero,
        "descricao": descricao,
        "tecnologia": tecnologia,
        "configuracoes": {
            "autenticacao_e_rede": {
                "nome_de_usuario_de_saida": numero,
                "nome_de_usuario_remoto": remote_username or numero,
                "segredo_local": local_secret,
                "segredo_remoto": remote_secret,
                "identificar_por": "Auth Username",
                "porta": porta,
            },
        },
    }


def _batch_trunk_json(entries=None):
    entries = entries if entries is not None else [
        _batch_trunk_entry(),
        _batch_trunk_entry(numero="1780", descricao="1780 - Camboriu"),
    ]
    return json.dumps({"ramais": entries}).encode()


CONDOMINIUM_NAMES = {"1020": "Parque Portugal", "1780": "Camboriu"}


def test_parse_batch_json_rejects_oversized_content():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_too_large"):
        parse_trunk_json_batch(_batch_trunk_json(), condominium_names=CONDOMINIUM_NAMES, max_bytes=10)


def test_parse_batch_json_rejects_invalid_json():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_invalid"):
        parse_trunk_json_batch(b"{not valid json", condominium_names=CONDOMINIUM_NAMES)


def test_parse_batch_json_rejects_non_dict_document():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_schema_invalid"):
        parse_trunk_json_batch(json.dumps([1, 2]).encode(), condominium_names=CONDOMINIUM_NAMES)


def test_parse_batch_json_rejects_non_dict_entry():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    content = json.dumps({"ramais": ["not-a-dict"]}).encode()

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_schema_invalid"):
        parse_trunk_json_batch(content, condominium_names=CONDOMINIUM_NAMES)


def test_parse_batch_json_rejects_non_dict_connection():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    entry = _batch_trunk_entry()
    entry["configuracoes"]["autenticacao_e_rede"] = "not-a-dict"
    content = json.dumps({"ramais": [entry]}).encode()

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_schema_invalid"):
        parse_trunk_json_batch(content, condominium_names=CONDOMINIUM_NAMES)


def test_parse_batch_json_maps_every_trunk_with_explicit_condominium():
    # Arrange
    from src.services.trunk_import import parse_trunk_json_batch

    # Act
    rows = parse_trunk_json_batch(_batch_trunk_json(), condominium_names=CONDOMINIUM_NAMES)

    # Assert
    assert [row.auth_username for row in rows] == ["1020", "1780"]
    assert [row.condominium_name for row in rows] == ["Parque Portugal", "Camboriu"]
    assert all(row.sip_profile == "internal-7060" for row in rows)
    assert all(row.prefix is None for row in rows)
    assert all("fixture-secret" not in repr(row) for row in rows)


def test_parse_batch_json_never_derives_condominium_or_prefix_from_description():
    # Arrange
    from src.services.trunk_import import parse_trunk_json_batch

    entries = [_batch_trunk_entry(numero="1780", descricao="1780 - Nome Errado No Arquivo")]

    # Act
    rows = parse_trunk_json_batch(
        _batch_trunk_json(entries), condominium_names={"1780": "Camboriu"}
    )

    # Assert
    assert rows[0].condominium_name == "Camboriu"
    assert rows[0].prefix is None


def test_parse_batch_json_rejects_trunk_without_explicit_condominium():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    # Act
    with pytest.raises(CSVSchemaError) as error:
        parse_trunk_json_batch(_batch_trunk_json(), condominium_names={"1020": "Parque Portugal"})

    # Assert
    assert str(error.value) == "trunk_json_condominium_missing"


def test_parse_batch_json_rejects_whole_batch_when_one_item_is_invalid():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    entries = [
        _batch_trunk_entry(),
        _batch_trunk_entry(numero="1780", descricao="1780 - Camboriu", porta=5060),
    ]

    # Act
    with pytest.raises(CSVSchemaError) as error:
        parse_trunk_json_batch(_batch_trunk_json(entries), condominium_names=CONDOMINIUM_NAMES)

    # Assert
    assert str(error.value) == "trunk_json_sip_configuration_invalid"


def test_parse_batch_json_rejects_secret_mismatch_without_leaking_values():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    local = "local-canary-secret"
    remote = "remote-canary-secret"
    entries = [_batch_trunk_entry(local_secret=local, remote_secret=remote)]

    # Act
    with pytest.raises(CSVSchemaError) as error:
        parse_trunk_json_batch(_batch_trunk_json(entries), condominium_names=CONDOMINIUM_NAMES)

    # Assert
    assert str(error.value) == "trunk_json_credentials_mismatch"
    assert local not in str(error.value)
    assert remote not in str(error.value)


def test_parse_batch_json_rejects_username_mismatch_between_outgoing_and_remote():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    entries = [_batch_trunk_entry(remote_username="9999")]

    # Act
    with pytest.raises(CSVSchemaError) as error:
        parse_trunk_json_batch(_batch_trunk_json(entries), condominium_names=CONDOMINIUM_NAMES)

    # Assert
    assert str(error.value) == "trunk_json_username_mismatch"


def test_parse_batch_json_rejects_document_without_ramais_list():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    # Act
    with pytest.raises(CSVSchemaError) as error:
        parse_trunk_json_batch(json.dumps({"ramais": {}}).encode(), condominium_names={})

    # Assert
    assert str(error.value) == "trunk_json_schema_invalid"


def test_parse_batch_json_enforces_item_limit():
    # Arrange
    from src.services.trunk_import import CSVSchemaError, parse_trunk_json_batch

    entries = [_batch_trunk_entry(numero=str(1000 + index)) for index in range(4)]
    names = {str(1000 + index): "Condominio" for index in range(4)}

    # Act
    with pytest.raises(CSVSchemaError) as error:
        parse_trunk_json_batch(_batch_trunk_json(entries), condominium_names=names, max_items=3)

    # Assert
    assert str(error.value) == "trunk_json_too_many_items"


@pytest.mark.asyncio
async def test_import_batch_json_dry_run_never_persists_or_encrypts():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunk_import import import_trunk_json_batch

    service = AsyncMock()

    # Act
    result = await import_trunk_json_batch(
        _batch_trunk_json(),
        "tenant-a",
        "pbx-1",
        condominium_names=CONDOMINIUM_NAMES,
        condominium_ids={"Parque Portugal": "condo-1", "Camboriu": "condo-2"},
        dry_run=True,
        trunk_service=service,
    )

    # Assert
    assert result.dry_run is True
    assert result.rows == 2
    service.upsert_imported.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_batch_json_rejects_when_condominium_mapping_missing_before_encrypting():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunk_import import CSVSchemaError, import_trunk_json_batch

    service = AsyncMock()

    # Act
    with pytest.raises(CSVSchemaError, match="trunk_json_condominium_missing"):
        await import_trunk_json_batch(
            _batch_trunk_json(),
            "tenant-a",
            "pbx-1",
            condominium_names=CONDOMINIUM_NAMES,
            condominium_ids={"Parque Portugal": "condo-1"},
            dry_run=False,
            trunk_service=service,
        )

    # Assert
    service.validate_importable.assert_not_awaited()
    service.upsert_imported.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_batch_json_counts_updated_and_unchanged_outcomes():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunk_import import import_trunk_json_batch

    service = AsyncMock()
    service.upsert_imported.side_effect = ["updated", "unchanged"]

    # Act
    result = await import_trunk_json_batch(
        _batch_trunk_json(),
        "tenant-a",
        "pbx-1",
        condominium_names=CONDOMINIUM_NAMES,
        condominium_ids={"Parque Portugal": "condo-1", "Camboriu": "condo-2"},
        dry_run=False,
        trunk_service=service,
    )

    # Assert
    assert result.updated == 1
    assert result.unchanged == 1


@pytest.mark.asyncio
async def test_import_batch_json_rejects_whole_batch_without_persisting_when_one_item_would_fail():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunk_import import import_trunk_json_batch
    from src.services.trunks import DuplicateIdentityError

    service = AsyncMock()
    service.validate_importable.side_effect = [None, DuplicateIdentityError("duplicate_auth_identity")]

    # Act
    with pytest.raises(DuplicateIdentityError):
        await import_trunk_json_batch(
            _batch_trunk_json(),
            "tenant-a",
            "pbx-1",
            condominium_names=CONDOMINIUM_NAMES,
            condominium_ids={"Parque Portugal": "condo-1", "Camboriu": "condo-2"},
            dry_run=False,
            trunk_service=service,
        )

    # Assert
    service.upsert_imported.assert_not_awaited()
    assert service.validate_importable.await_count == 2


@pytest.mark.asyncio
async def test_import_batch_json_persists_each_trunk_under_its_condominium():
    # Arrange
    from unittest.mock import AsyncMock

    from src.services.trunk_import import import_trunk_json_batch

    service = AsyncMock()
    service.upsert_imported.return_value = "created"

    # Act
    result = await import_trunk_json_batch(
        _batch_trunk_json(),
        "tenant-a",
        "pbx-1",
        condominium_names=CONDOMINIUM_NAMES,
        condominium_ids={"Parque Portugal": "condo-1", "Camboriu": "condo-2"},
        dry_run=False,
        trunk_service=service,
    )

    # Assert
    assert result.created == 2
    persisted = [call.kwargs["row"] for call in service.upsert_imported.await_args_list]
    assert [row.condominium_id for row in persisted] == ["condo-1", "condo-2"]
