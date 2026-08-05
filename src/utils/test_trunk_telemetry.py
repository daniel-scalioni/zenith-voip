
def _metrics():
    from src.utils.telemetry import (
        trunk_active_calls,
        trunk_directory_lookups_total,
        trunk_reconciliation_total,
        trunk_registration_state,
    )

    return trunk_active_calls, trunk_directory_lookups_total, trunk_reconciliation_total, trunk_registration_state


def test_trunk_metrics_use_only_bounded_labels():
    # Arrange
    metrics = _metrics()
    forbidden = {"tenant_id", "username", "prefix", "ip", "password", "trunk_id"}

    # Act
    label_sets = [set(metric._labelnames) for metric in metrics]

    # Assert
    assert all(labels.isdisjoint(forbidden) for labels in label_sets)
    assert set(metrics[1]._labelnames) <= {"result", "profile"}
