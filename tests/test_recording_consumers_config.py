from src.config import Settings


def test_recording_defaults_match_operational_decisions():
    # Arrange / Act
    config = Settings(_env_file=None)

    # Assert
    assert config.RECORDING_REQUIRED_CONSUMERS == ["smb"]
    assert config.RECORDING_MAX_CALL_SECONDS == 300
    assert config.RECORDING_MIN_FREE_PERCENT == 20
    assert config.RECORDING_RESUME_FREE_PERCENT == 30
    assert config.RECORDING_PROCESSING_HEADROOM_BYTES == 134_217_728
    assert config.RECORDING_LEASE_TTL_SECONDS == 120
    assert config.RECORDING_LEASE_HEARTBEAT_SECONDS == 30
    assert config.RECORDING_CLEANUP_ROUND_SECONDS == 900
