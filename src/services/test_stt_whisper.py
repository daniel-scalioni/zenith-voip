import json
import asyncio
from types import SimpleNamespace

import pytest

from src.services import stt_whisper


@pytest.mark.asyncio
async def test_transcribe_reports_missing_binary(monkeypatch):
    # Arrange
    strategy = stt_whisper.WhisperCppSTT()
    monkeypatch.setattr(stt_whisper.shutil, "which", lambda _name: None)

    # Act
    result = await strategy.transcribe(b"RIFF")

    # Assert
    assert result == {"text": "", "confidence": 0.0, "error": "whisper-cpp not installed"}


@pytest.mark.asyncio
async def test_transcribe_reads_json_sidecar_and_normalizes_log_probability(monkeypatch):
    # Arrange
    strategy = stt_whisper.WhisperCppSTT(binary="whisper-cli")
    monkeypatch.setattr(stt_whisper.shutil, "which", lambda _name: "/usr/bin/whisper-cli")

    async def completed(command, _timeout):
        assert command[-6:] == ["-ojf", "-sns", "-l", "pt", "-t", "1"]
        sidecar = stt_whisper.Path(command[command.index("-f") + 1] + ".json")
        sidecar.write_text(json.dumps({
            "transcription": [{
                "text": " bom dia ",
                "offsets": {"from": 120, "to": 340},
                "avg_logprob": -0.223143551,
            }],
        }), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(stt_whisper, "_run_whisper", completed)

    # Act
    result = await strategy.transcribe(b"RIFF")

    # Assert
    assert result["text"] == "bom dia"
    assert result["confidence"] == pytest.approx(0.8)
    assert result["segments"] == [{
        "text": "bom dia", "start": 0.12, "end": 0.34, "confidence": pytest.approx(0.8)
    }]


@pytest.mark.asyncio
async def test_transcribe_returns_error_for_invalid_sidecar_and_cleans_files(monkeypatch, tmp_path):
    # Arrange
    strategy = stt_whisper.WhisperCppSTT()
    monkeypatch.setattr(stt_whisper.shutil, "which", lambda _name: "/bin/whisper-cpp")
    created = []

    def named_file(**kwargs):
        handle = stt_whisper.tempfile.NamedTemporaryFile(dir=tmp_path, **kwargs)
        created.append(stt_whisper.Path(handle.name))
        return handle

    monkeypatch.setattr(stt_whisper, "_named_audio_file", named_file)

    async def completed(command, _timeout):
        stt_whisper.Path(command[command.index("-f") + 1] + ".json").write_text("[]", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(stt_whisper, "_run_whisper", completed)

    # Act
    result = await strategy.transcribe(b"RIFF")

    # Assert
    assert "invalid whisper JSON" in result["error"]
    assert all(not path.exists() and not stt_whisper.Path(str(path) + ".json").exists() for path in created)


@pytest.mark.asyncio
async def test_transcribe_propagates_process_failure_as_result(monkeypatch):
    # Arrange
    strategy = stt_whisper.WhisperCppSTT()
    monkeypatch.setattr(stt_whisper.shutil, "which", lambda _name: "/bin/whisper-cpp")
    async def failed(_command, _timeout):
        return SimpleNamespace(returncode=2, stdout="", stderr="model failed")

    monkeypatch.setattr(stt_whisper, "_run_whisper", failed)

    # Act
    result = await strategy.transcribe(b"RIFF")

    # Assert
    assert result["confidence"] == 0.0
    assert result["error"] == "model failed"


def test_parse_sidecar_uses_mean_token_probability_when_logprob_is_absent():
    # Arrange
    payload = {"transcription": [{
        "text": "teste", "offsets": {"from": 0, "to": 100},
        "tokens": [{"p": 0.6}, {"p": 0.8}],
    }]}

    # Act
    result = stt_whisper._parse_sidecar(payload)

    # Assert
    assert result[0]["confidence"] == pytest.approx(0.7)


def test_parse_sidecar_prefers_token_probability_over_logprob_fallback():
    # Arrange
    payload = {"transcription": [{
        "text": "teste", "offsets": {"from": 0, "to": 100},
        "tokens": [{"p": 0.6}, {"p": 0.8}], "avg_logprob": -10,
    }]}

    # Act
    result = stt_whisper._parse_sidecar(payload)

    # Assert
    assert result[0]["confidence"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_run_whisper_kills_process_when_cancelled(monkeypatch):
    # Arrange
    started = asyncio.Event()

    class Process:
        returncode = None
        killed = False
        waited = False

        async def communicate(self):
            started.set()
            await asyncio.Event().wait()

        def kill(self):
            self.killed = True
            self.returncode = -9

        async def wait(self):
            self.waited = True

    process = Process()
    monkeypatch.setattr(
        stt_whisper.asyncio,
        "create_subprocess_exec",
        lambda *_args, **_kwargs: _async_process(process),
    )
    task = asyncio.create_task(stt_whisper._run_whisper(["whisper-cli"], 60))
    await started.wait()

    # Act
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Assert
    assert process.killed
    assert process.waited


async def _async_process(process):
    return process
