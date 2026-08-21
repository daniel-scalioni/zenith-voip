import inspect
from unittest.mock import MagicMock

import pytest

from src.services.tts_service import PiperTTS


def test_synthesize_signature_does_not_declare_voice_or_speaker_id():
    # Arrange / Act: GAP-RE-10 — a assinatura prometia voice/speaker_id mas os ignorava
    params = inspect.signature(PiperTTS.synthesize).parameters

    # Assert
    assert "voice" not in params
    assert "speaker_id" not in params


def _fake_synthesize_wav(text, wav_file):
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(16000)
    wav_file.writeframes(b"\x00\x00")


@pytest.mark.asyncio
async def test_synthesize_returns_bytes_from_loaded_voice(monkeypatch):
    # Arrange
    tts = PiperTTS(model_path="fake-model.onnx")
    fake_voice = MagicMock()
    fake_voice.synthesize_wav = _fake_synthesize_wav
    monkeypatch.setattr("src.services.tts_service._load_voice", lambda _path: fake_voice)

    # Act
    result = await tts.synthesize("ola mundo")

    # Assert
    assert isinstance(result, bytes)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_synthesize_accepts_and_ignores_unknown_kwargs_for_strategy_compat(monkeypatch):
    # Arrange: TTSStrategy.execute repassa **kwargs livremente; um chamador que ainda
    # passe voice/speaker_id não pode quebrar a chamada, mesmo que o valor seja ignorado
    tts = PiperTTS(model_path="fake-model.onnx")
    fake_voice = MagicMock()
    fake_voice.synthesize_wav = _fake_synthesize_wav
    monkeypatch.setattr("src.services.tts_service._load_voice", lambda _path: fake_voice)

    # Act
    result = await tts.synthesize("ola", voice="pt_BR", speaker_id=3)

    # Assert
    assert isinstance(result, bytes)
