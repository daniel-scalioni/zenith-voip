from src.utils import telemetry


def test_recording_telemetry_tracks_capacity_refusal_cleanup_and_lease_failure():
    # Arrange
    refused_before = telemetry.recording_refused_total._value.get()
    candidates_before = telemetry.recording_temp_candidates_total._value.get()
    deleted_before = telemetry.recording_temp_deleted_total._value.get()
    lease_before = telemetry.recording_lease_failures_total.labels(stage="capture")._value.get()

    # Act
    telemetry.set_recording_capacity(used_bytes=100, reserved_bytes=200, total_bytes=1000, degraded=True)
    telemetry.record_recording_refused()
    telemetry.record_temporary_cleanup(candidates=2, deleted=1)
    telemetry.record_lease_failure("capture")

    # Assert
    assert telemetry.recording_storage_used_bytes._value.get() == 100
    assert telemetry.recording_reserved_bytes._value.get() == 200
    assert telemetry.recording_storage_total_bytes._value.get() == 1000
    assert telemetry.recording_degraded_mode._value.get() == 1
    assert telemetry.recording_refused_total._value.get() == refused_before + 1
    assert telemetry.recording_temp_candidates_total._value.get() == candidates_before + 2
    assert telemetry.recording_temp_deleted_total._value.get() == deleted_before + 1
    assert telemetry.recording_lease_failures_total.labels(stage="capture")._value.get() == lease_before + 1


def test_transcript_telemetry_tracks_backlog_shed_by_capacity():
    # Arrange
    before = telemetry.transcript_backlog_dropped_total.labels(tenant_id="tenant-a")._value.get()

    # Act
    telemetry.record_transcript_backlog_dropped("tenant-a")

    # Assert
    assert telemetry.transcript_backlog_dropped_total.labels(
        tenant_id="tenant-a"
    )._value.get() == before + 1
