import tempfile
import json
import math
import shutil
import asyncio
from types import SimpleNamespace
from pathlib import Path

from src.services.base import STTStrategy


def _named_audio_file(**kwargs):
    return tempfile.NamedTemporaryFile(**kwargs)


async def _run_whisper(command: list[str], timeout_seconds: int):
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    return SimpleNamespace(
        returncode=process.returncode,
        stdout=stdout.decode(errors="replace"),
        stderr=stderr.decode(errors="replace"),
    )


def _confidence(segment: dict) -> float:
    probabilities = [
        float(token["p"])
        for token in segment.get("tokens", [])
        if isinstance(token, dict) and isinstance(token.get("p"), (int, float))
    ]
    if probabilities:
        return min(1.0, max(0.0, sum(probabilities) / len(probabilities)))
    if "avg_logprob" in segment:
        return min(1.0, max(0.0, math.exp(float(segment["avg_logprob"]))))
    return 0.0


def _parse_sidecar(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("invalid whisper JSON root")
    raw_segments = payload.get("transcription", payload.get("segments"))
    if not isinstance(raw_segments, list):
        raise ValueError("invalid whisper JSON segments")
    segments = []
    for raw in raw_segments:
        if not isinstance(raw, dict):
            raise ValueError("invalid whisper JSON segment")
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        offsets = raw.get("offsets", {})
        start = raw.get("start", offsets.get("from", 0))
        end = raw.get("end", offsets.get("to", start))
        if "offsets" in raw:
            start = float(start) / 1000.0
            end = float(end) / 1000.0
        segments.append({
            "text": text,
            "start": float(start),
            "end": float(end),
            "confidence": _confidence(raw),
        })
    return segments


class WhisperCppSTT(STTStrategy):
    def __init__(
        self,
        model_path: str = "/models/ggml-base.bin",
        binary: str = "whisper-cpp",
        timeout_seconds: int = 300,
        language: str = "pt",
        threads: int = 1,
    ):
        self.model_path = model_path
        self.whisper_binary = binary
        self.timeout_seconds = timeout_seconds
        self.language = language
        self.threads = threads

    async def transcribe(self, audio_chunk: bytes, **kwargs) -> dict:
        binary = shutil.which(self.whisper_binary)
        if binary is None:
            return {"text": "", "confidence": 0.0, "error": "whisper-cpp not installed"}

        with _named_audio_file(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_chunk)
            tmp_path = Path(tmp.name)
        sidecar = Path(str(tmp_path) + ".json")

        try:
            result = await _run_whisper(
                [
                    binary, "-m", self.model_path, "-f", str(tmp_path),
                    "-ojf", "-sns", "-l", self.language, "-t", str(self.threads),
                ],
                self.timeout_seconds,
            )
            if result.returncode != 0:
                return {"text": "", "confidence": 0.0, "error": result.stderr.strip()}

            if not sidecar.is_file():
                raise ValueError("whisper JSON sidecar was not created")
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            segments = _parse_sidecar(data)
            confidences = [segment["confidence"] for segment in segments]
            return {
                "text": " ".join(segment["text"] for segment in segments),
                "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
                "segments": segments,
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError, asyncio.TimeoutError) as exc:
            return {"text": "", "confidence": 0.0, "error": str(exc)}
        finally:
            tmp_path.unlink(missing_ok=True)
            sidecar.unlink(missing_ok=True)
