from deepgram import DeepgramClient, PrerecordedOptions
from src.services.base import STTStrategy
from src.config import settings


class DeepgramSTT(STTStrategy):
    def __init__(self):
        self.client = DeepgramClient(settings.DEEPGRAM_API_KEY) if settings.DEEPGRAM_API_KEY else None

    async def transcribe(self, audio_chunk: bytes, **kwargs) -> dict:
        if not self.client:
            return {"text": "", "confidence": 0.0, "error": "Deepgram not configured"}

        options = PrerecordedOptions(
            model="nova-2",
            language="pt",
            diarize=True,
            punctuate=True,
        )

        source = {"buffer": audio_chunk, "mimetype": kwargs.get("mimetype", "audio/wav")}
        response = await self.client.listen.prerecorded.v("1").transcribe(source, options)
        return self._parse_response(response)

    def _parse_response(self, response) -> dict:
        try:
            results = response.results
            channels = results.channels
            if not channels:
                return {"text": "", "confidence": 0.0}

            channel = channels[0]
            alternatives = channel.alternatives
            if not alternatives:
                return {"text": "", "confidence": 0.0}

            best = alternatives[0]
            return {
                "text": best.transcript,
                "confidence": best.confidence,
                "words": [{"word": w.word, "start": w.start, "end": w.end, "speaker": w.speaker} for w in best.words] if best.words else [],
            }
        except Exception as e:
            return {"text": "", "confidence": 0.0, "error": str(e)}
