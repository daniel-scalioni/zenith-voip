import pytest
from pydantic import ValidationError

from src.config import Settings


def test_smb_defaults_are_disabled_and_safe():
    # Arrange / Act
    config = Settings(_env_file=None)

    # Assert
    assert config.SMB_ENABLED is False
    assert config.SMB_PORT == 445
    assert config.SMB_IS_DIRECT_TCP is True
    assert config.SMB_USE_NTLM_V2 is True
    assert config.SMB_SIGN_OPTIONS == 2
    assert config.SMB_BANDWIDTH_LIMIT_MBS == 5
    assert config.SMB_TRANSFER_LOG_PATH == "/data/smb_logs/smb_transfer_log.json"
    assert config.SMB_SYNC_INTERVAL_MINUTES == 5


def test_smb_enabled_requires_connection_fields():
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        Settings(SMB_ENABLED=True, _env_file=None)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("SMB_PORT", 0),
        ("SMB_BANDWIDTH_LIMIT_MBS", 0),
        ("SMB_SYNC_INTERVAL_MINUTES", 0),
        ("SMB_CLIENT_NAME", "CLIENT-NAME-TOO-LONG"),
    ],
)
def test_smb_rejects_invalid_limits(field, value):
    # Arrange
    values = {
        "SMB_ENABLED": True,
        "SMB_HOST": "storage",
        "SMB_SERVER_NAME": "STORAGE",
        "SMB_SHARE": "backup",
        "SMB_USERNAME": "worker",
        "SMB_PASSWORD": "secret",
        field: value,
    }

    # Act / Assert
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)
