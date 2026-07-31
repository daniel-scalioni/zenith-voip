from src.utils import telemetry


def test_smb_metric_helpers_update_without_call_id_label():
    # Arrange
    before_success = telemetry.smb_backup_success_total._value.get()
    before_failure = telemetry.smb_backup_failed_total._value.get()

    # Act
    telemetry.record_smb_success()
    telemetry.record_smb_failure()
    telemetry.observe_smb_latency(0.25)
    telemetry.set_smb_queue_size(3)
    telemetry.set_smb_conversion_pending(2)

    # Assert
    assert telemetry.smb_backup_success_total._value.get() == before_success + 1
    assert telemetry.smb_backup_failed_total._value.get() == before_failure + 1
    assert telemetry.smb_backup_queue_size._value.get() == 3
    assert telemetry.smb_conversion_pending._value.get() == 2
    assert "call_id" not in telemetry.smb_backup_success_total._labelnames
