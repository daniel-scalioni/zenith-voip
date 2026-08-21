import json

import pytest

from src.workers.recording_consumers import is_fully_consumed, mark_consumed


def test_mark_consumed_is_atomic_and_requires_all_consumers(tmp_path):
    # Arrange / Act
    marker = mark_consumed(tmp_path, "smb")

    # Assert
    assert marker.name == ".consumed-smb"
    assert json.loads(marker.read_text())["consumer"] == "smb"
    assert is_fully_consumed(tmp_path, ["smb"])
    assert not is_fully_consumed(tmp_path, ["smb", "transcription"])
    assert not is_fully_consumed(tmp_path, [])
    mark_consumed(tmp_path, "transcription")
    assert is_fully_consumed(tmp_path, ["smb", "transcription"])


def test_mark_consumed_rejects_unsafe_consumer_name(tmp_path):
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        mark_consumed(tmp_path, "../bad")
