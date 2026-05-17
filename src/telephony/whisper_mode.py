from src.telephony.esl_client import esl_client
from src.services.tts_fallback import TTSWithFallback


class WhisperMode:
    def __init__(self):
        self.tts = TTSWithFallback()

    async def whisper_to_agent(self, call_id: str, text: str) -> dict:
        agent_uuid = esl_client.get_agent_uuid(call_id)
        if not agent_uuid:
            return {"success": False, "error": "agent_uuid not found"}

        audio_bytes = await self.tts.synthesize(text)
        if not audio_bytes:
            return {"success": False, "error": "TTS synthesis failed"}

        temp_file = f"/tmp/whisper_{call_id}.wav"
        with open(temp_file, "wb") as f:
            f.write(audio_bytes)

        command = f"uuid_play {agent_uuid} {temp_file}"
        response = await esl_client.send_api(command)
        return {"success": True, "command": command, "response": response}
