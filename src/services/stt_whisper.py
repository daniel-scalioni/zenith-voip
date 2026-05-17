import subprocess
import tempfile
import json
import os
from src.services.base import STTStrategy


class WhisperCppSTT(STTStrategy):
    def __init__(self, model_path: str = "/models/ggml-base.bin"):
        self.model_path = model_path
        self.whisper_binary = "whisper-cpp"

    async def transcribe(self, audio_chunk: bytes, **kwargs) -> dict:
        if not os.path.exists(self.whisper_binary):
            return {"text": "", "confidence": 0.0, "error": "whisper-cpp not installed"}

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_chunk)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [self.whisper_binary, "-m", self.model_path, "-f", tmp_path, "-oj"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return {"text": "", "confidence": 0.0, "error": result.stderr}

            data = json.loads(result.stdout)
            return {
                "text": data.get("text", ""),
                "confidence": data.get("avg_logprob", 0.0),
                "segments": data.get("segments", []),
            }
        except Exception as e:
            return {"text": "", "confidence": 0.0, "error": str(e)}
        finally:
            os.unlink(tmp_path)
