import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint


def _models():
    from src.database.models import ATATrunk, Condominium

    return Condominium, ATATrunk


def test_condominium_model_uses_public_schema_and_tenant_scoped_identity():
    # Arrange
    Condominium, _ = _models()

    # Act
    constraints = list(Condominium.__table__.constraints)

    # Assert
    assert Condominium.__table__.schema == "public"
    assert {"tenant_id", "pbx_id", "name"} in [
        {column.name for column in constraint.columns}
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    ]


def test_ata_trunk_model_enforces_authentication_identity():
    # Arrange
    _, ATATrunk = _models()

    # Act
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in ATATrunk.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    # Assert
    assert ATATrunk.__table__.schema == "public"
    assert ("sip_profile", "auth_username") in unique_columns


def test_ata_trunk_prefix_is_nullable_and_unique_only_when_present():
    # Arrange
    _, ATATrunk = _models()

    # Act
    prefix = ATATrunk.__table__.columns["prefix"]
    matching_indexes = [
        index for index in ATATrunk.__table__.indexes
        if index.unique and tuple(column.name for column in index.columns) == ("tenant_id", "prefix")
    ]

    # Assert
    assert prefix.nullable is True
    assert len(matching_indexes) == 1
    assert "prefix IS NOT NULL" in str(matching_indexes[0].dialect_options["postgresql"]["where"])


@pytest.mark.parametrize(
    ("column", "nullable"),
    [("encrypted_password", False), ("registration_status", False), ("enabled", False)],
)
def test_ata_trunk_sensitive_and_state_columns_are_explicit(column, nullable):
    # Arrange
    _, ATATrunk = _models()

    # Act
    model_column = ATATrunk.__table__.columns[column]

    # Assert
    assert model_column.nullable is nullable
    assert any(isinstance(item, CheckConstraint) for item in ATATrunk.__table__.constraints)
