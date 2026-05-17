from src.telephony.esl_client import esl_client


FILLER_PHRASES = {
    "processing": "/usr/share/freeswitch/sounds/zenith/filler_processing.wav",
    "please_wait": "/usr/share/freeswitch/sounds/zenith/filler_please_wait.wav",
    "default": "/usr/share/freeswitch/sounds/zenith/filler_processing.wav",
}


class FillerAudio:
    async def play_to_customer(self, call_id: str, phrase: str = "default") -> dict:
        customer_uuid = esl_client.get_customer_uuid(call_id)
        if not customer_uuid:
            return {"success": False, "error": "customer_uuid not found"}

        wav_path = FILLER_PHRASES.get(phrase, FILLER_PHRASES["default"])
        command = f"uuid_play {customer_uuid} {wav_path}"
        response = await esl_client.send_api(command)
        return {"success": True, "command": command, "response": response}
