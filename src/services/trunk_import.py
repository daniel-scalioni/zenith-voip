"""Parser sanitizado e executor idempotente de CSV de troncos ATA."""

import csv
import io
import json
from dataclasses import dataclass, field, replace


class CSVSchemaError(ValueError):
    pass


_ROW_ERROR_FIELDS = {
    "pbx_not_found": "pbx_id",
    "condominium_not_found": "condominium_id",
    "duplicate_auth_identity": "auth_username",
    "duplicate_prefix": "prefix",
    "invalid_prefix": "prefix",
    "invalid_password": "password",
    "invalid_sip_configuration": "sip_profile",
}


@dataclass(frozen=True)
class TrunkCSVRow:
    line: int
    prefix: str | None
    condominium_name: str
    auth_username: str
    password: str = field(repr=False)
    sip_profile: str = "internal"
    condominium_id: str | None = None


@dataclass(frozen=True)
class ParsedTrunkCSV:
    rows: list[TrunkCSVRow]
    ignored: int


@dataclass
class TrunkImportResult:
    dry_run: bool
    rows: int
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    errors: list[dict] = field(default_factory=list)


def parse_trunk_csv(content: bytes, *, max_rows: int = 10_000, max_bytes: int = 5 * 1024 * 1024) -> ParsedTrunkCSV:
    if not isinstance(content, bytes) or len(content) > max_bytes:
        raise CSVSchemaError("csv_too_large")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CSVSchemaError("csv_encoding_invalid") from error
    reader = csv.DictReader(io.StringIO(text))
    required = {"technology", "device_user", "device_password"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise CSVSchemaError("csv_schema_invalid")
    rows: list[TrunkCSVRow] = []
    ignored = 0
    processed = 0
    for line, raw in enumerate(reader, start=2):
        processed += 1
        if processed > max_rows:
            raise CSVSchemaError("csv_row_limit")
        technology = (raw.get("technology") or "").strip().lower()
        if technology == "virtual":
            ignored += 1
            continue
        if technology not in {"sip", "pjsip"}:
            ignored += 1
            continue
        username = (raw.get("device_user") or "").strip()
        password = raw.get("device_password") or ""
        if not username or not password:
            raise CSVSchemaError("csv_row_invalid")
        rows.append(TrunkCSVRow(
            line=line,
            prefix=(raw.get("prefix") or raw.get("extension") or "").strip() or None,
            condominium_name=(raw.get("condominium") or raw.get("ext_name") or "").strip(),
            auth_username=username,
            password=password,
            sip_profile="internal-7060" if technology == "pjsip" else "internal",
            condominium_id=(raw.get("condominium_id") or "").strip() or None,
        ))
    return ParsedTrunkCSV(rows=rows, ignored=ignored)


async def import_trunk_csv(content, tenant_id, pbx_id, *, dry_run, trunk_service) -> TrunkImportResult:
    from src.services.trunks import DuplicateIdentityError, ScopeValidationError

    parsed = parse_trunk_csv(content)
    result = TrunkImportResult(dry_run=dry_run, rows=len(parsed.rows), unchanged=parsed.ignored)
    if dry_run:
        return result
    for row in parsed.rows:
        try:
            outcome = await trunk_service.upsert_imported(tenant_id=tenant_id, pbx_id=pbx_id, row=row)
        except (ScopeValidationError, DuplicateIdentityError, ValueError) as error:
            code = str(error)
            result.rejected += 1
            result.errors.append({
                "line": row.line, "code": code, "field": _ROW_ERROR_FIELDS.get(code),
            })
            continue
        if outcome == "created":
            result.created += 1
        elif outcome == "updated":
            result.updated += 1
        else:
            result.unchanged += 1
    return result


def parse_trunk_json(
    content: bytes,
    *,
    condominium_name: str,
    max_bytes: int = 256 * 1024,
) -> TrunkCSVRow:
    if not isinstance(content, bytes) or len(content) > max_bytes:
        raise CSVSchemaError("trunk_json_too_large")
    try:
        document = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CSVSchemaError("trunk_json_invalid") from error
    if not isinstance(document, dict) or not condominium_name.strip():
        raise CSVSchemaError("trunk_json_schema_invalid")
    general = document.get("configuracoes_gerais")
    connection = document.get("general_configurations")
    if not isinstance(general, dict) or not isinstance(connection, dict):
        raise CSVSchemaError("trunk_json_schema_invalid")

    return _normalize_trunk_entry(
        technology=general.get("tecnologia"),
        connection=connection,
        condominium_name=condominium_name,
        line=1,
    )


def _normalize_trunk_entry(*, technology, connection, condominium_name: str, line: int) -> TrunkCSVRow:
    technology = str(technology or "").strip().lower()
    try:
        port = int(connection.get("porta"))
    except (TypeError, ValueError) as error:
        raise CSVSchemaError("trunk_json_sip_configuration_invalid") from error
    if technology != "pjsip" or port != 7060:
        raise CSVSchemaError("trunk_json_sip_configuration_invalid")

    remote_username = str(connection.get("nome_de_usuario_remoto") or "").strip()
    outgoing_username = str(connection.get("nome_de_usuario_de_saida") or "").strip()
    if not remote_username:
        raise CSVSchemaError("trunk_json_username_missing")
    if outgoing_username and outgoing_username != remote_username:
        raise CSVSchemaError("trunk_json_username_mismatch")

    remote_secret = connection.get("segredo_remoto")
    local_secret = connection.get("segredo_local")
    if not isinstance(remote_secret, str) or not remote_secret:
        raise CSVSchemaError("trunk_json_secret_missing")
    if local_secret not in (None, "", remote_secret):
        raise CSVSchemaError("trunk_json_credentials_mismatch")

    return TrunkCSVRow(
        line=line,
        prefix=None,
        condominium_name=condominium_name.strip(),
        auth_username=remote_username,
        password=remote_secret,
        sip_profile="internal-7060",
    )


def parse_trunk_json_batch(
    content: bytes,
    *,
    condominium_names: dict,
    max_items: int = 500,
    max_bytes: int = 1024 * 1024,
) -> list[TrunkCSVRow]:
    """Lê o veículo de exportação em lote (`ramais[]`) exigindo condomínio explícito por identidade."""
    if not isinstance(content, bytes) or len(content) > max_bytes:
        raise CSVSchemaError("trunk_json_too_large")
    try:
        document = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CSVSchemaError("trunk_json_invalid") from error
    if not isinstance(document, dict):
        raise CSVSchemaError("trunk_json_schema_invalid")

    entries = document.get("ramais")
    if not isinstance(entries, list) or not entries:
        raise CSVSchemaError("trunk_json_schema_invalid")
    if len(entries) > max_items:
        raise CSVSchemaError("trunk_json_too_many_items")

    rows = []
    for line, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise CSVSchemaError("trunk_json_schema_invalid")
        settings = entry.get("configuracoes")
        connection = settings.get("autenticacao_e_rede") if isinstance(settings, dict) else None
        if not isinstance(connection, dict):
            raise CSVSchemaError("trunk_json_schema_invalid")

        # A descrição do arquivo nunca vira condomínio: o mapa explícito é a única fonte.
        number = str(entry.get("numero") or "").strip()
        condominium_name = str(condominium_names.get(number) or "").strip() if number else ""
        if not condominium_name:
            raise CSVSchemaError("trunk_json_condominium_missing")

        rows.append(
            _normalize_trunk_entry(
                technology=entry.get("tecnologia"),
                connection=connection,
                condominium_name=condominium_name,
                line=line,
            )
        )
    return rows


async def import_trunk_json(
    content,
    tenant_id,
    pbx_id,
    *,
    condominium_name,
    condominium_id,
    dry_run,
    trunk_service,
) -> TrunkImportResult:
    row = parse_trunk_json(content, condominium_name=condominium_name)
    result = TrunkImportResult(dry_run=dry_run, rows=1)
    if dry_run:
        return result
    if not condominium_id:
        raise CSVSchemaError("trunk_json_condominium_missing")
    outcome = await trunk_service.upsert_imported(
        tenant_id=tenant_id,
        pbx_id=pbx_id,
        row=replace(row, condominium_id=condominium_id),
    )
    if outcome == "created":
        result.created = 1
    elif outcome == "updated":
        result.updated = 1
    else:
        result.unchanged = 1
    return result


async def import_trunk_json_batch(
    content,
    tenant_id,
    pbx_id,
    *,
    condominium_names: dict,
    condominium_ids: dict,
    dry_run: bool,
    trunk_service,
    max_items: int = 500,
) -> TrunkImportResult:
    rows = parse_trunk_json_batch(
        content, condominium_names=condominium_names, max_items=max_items
    )
    result = TrunkImportResult(dry_run=dry_run, rows=len(rows))
    if dry_run:
        return result

    # Falha fechada antes de cifrar qualquer credencial do lote.
    if any(not condominium_ids.get(row.condominium_name) for row in rows):
        raise CSVSchemaError("trunk_json_condominium_missing")

    resolved_rows = [
        replace(row, condominium_id=condominium_ids[row.condominium_name]) for row in rows
    ]

    # Tudo-ou-nada (design.md#Importação VitalPBX Exportada): valida cada item antes
    # de persistir o primeiro, para nunca deixar o lote parcialmente escrito.
    for row in resolved_rows:
        await trunk_service.validate_importable(tenant_id=tenant_id, pbx_id=pbx_id, row=row)

    for row in resolved_rows:
        outcome = await trunk_service.upsert_imported(
            tenant_id=tenant_id,
            pbx_id=pbx_id,
            row=row,
        )
        if outcome == "created":
            result.created += 1
        elif outcome == "updated":
            result.updated += 1
        else:
            result.unchanged += 1
    return result
