import asyncio
import json
import re
from collections import defaultdict
from src.config import settings
from src.events.redis_streams import event_bus
from src.services.calls import create_call_record, finalize_call_record
from src.workers.audio_uploader import enqueue_recording_upload

SIP_IP_KEY_TTL = 3600
SIP_EXT_PBX_KEY_TTL = 3600
WS_AGENT_SESSION_TTL = 30


class ESLClient:
    def __init__(self, host: str = settings.FREESWITCH_ESL_HOST, port: int = settings.FREESWITCH_ESL_PORT, password: str = settings.FREESWITCH_ESL_PASSWORD):
        self.host = host
        self.port = port
        self.password = password
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.connected = False
        self.uuid_map: dict[str, dict[str, str]] = {}
        self._listener_task: asyncio.Task | None = None
        self._running = False

    async def connect(self):
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=5.0
        )
        auth = f"auth {self.password}\n\n"
        self.writer.write(auth.encode())
        await self.writer.drain()
        response = await asyncio.wait_for(self.reader.read(4096), timeout=3.0)
        if b"+OK" not in response and b"OK" not in response:
            raise ConnectionError(f"ESL auth failed: {response}")

        self.writer.write(b"events json CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP SOFIA_REGISTER SOFIA_UNREGISTER\n\n")
        await self.writer.drain()
        self.connected = True

    async def send_api(self, command: str) -> str:
        if not self.connected:
            await self.connect()
        cmd = f"api {command}\n\n"
        self.writer.write(cmd.encode())
        await self.writer.drain()
        response = await asyncio.wait_for(self.reader.read(8192), timeout=10.0)
        return response.decode(errors="replace")

    async def send_bgapi(self, command: str) -> str:
        if not self.connected:
            await self.connect()
        cmd = f"bgapi {command}\n\n"
        self.writer.write(cmd.encode())
        await self.writer.drain()
        response = await asyncio.wait_for(self.reader.read(8192), timeout=5.0)
        return response.decode(errors="replace")

    def map_uuids(self, call_id: str, agent_uuid: str, customer_uuid: str):
        self.uuid_map[call_id] = {"agent": agent_uuid, "customer": customer_uuid}

    def get_agent_uuid(self, call_id: str) -> str | None:
        entry = self.uuid_map.get(call_id)
        return entry["agent"] if entry else None

    def get_customer_uuid(self, call_id: str) -> str | None:
        entry = self.uuid_map.get(call_id)
        return entry["customer"] if entry else None

    async def start_event_listener(self):
        if self._running:
            return
        self._running = True
        self._listener_task = asyncio.create_task(self._event_loop())

    async def stop_event_listener(self):
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            self._listener_task = None

    async def _event_loop(self):
        while self._running:
            try:
                if not self.connected:
                    await self.connect()
                await self._read_events()
            except (ConnectionError, asyncio.TimeoutError, OSError) as e:
                self.connected = False
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break

    async def _read_events(self):
        buffer = ""
        while self._running and self.connected:
            chunk = await asyncio.wait_for(self.reader.read(65536), timeout=30.0)
            if not chunk:
                raise ConnectionError("ESL connection closed")
            buffer += chunk.decode(errors="replace")
            while "\n\n" in buffer:
                raw_event, buffer = buffer.split("\n\n", 1)
                await self._process_event(raw_event.strip())

    async def _process_event(self, raw: str):
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return

        event_name = event.get("Event-Name", "")
        if event_name == "SOFIA_REGISTER":
            await self._handle_register(event)
        elif event_name == "SOFIA_UNREGISTER":
            await self._handle_unregister(event)
        elif event_name == "CHANNEL_CREATE":
            await self._handle_channel_create(event)
        elif event_name == "CHANNEL_ANSWER":
            await self._handle_channel_answer(event)
        elif event_name == "CHANNEL_HANGUP":
            await self._handle_channel_hangup(event)

    async def _handle_register(self, event: dict):
        from_user = event.get("Caller-Caller-ID-Number", "") or event.get("sip_from_user", "")
        from_host = event.get("Caller-Source", "") or event.get("sip_from_host", "")
        sip_ip = self._extract_ip(event)

        if not from_user or not sip_ip:
            return

        await self._cache_sip_mapping(from_user, sip_ip, event)

    async def _handle_unregister(self, event: dict):
        from_user = event.get("Caller-Caller-ID-Number", "") or event.get("sip_from_user", "")
        if from_user:
            await self._remove_sip_mapping(from_user)

    async def _handle_channel_create(self, event: dict):
        dest = event.get("Caller-Destination-Number", "")
        if dest == "*88":
            await self._handle_manual_linkage(event)

    async def _handle_channel_answer(self, event: dict):
        call_id = event.get("Caller-Unique-ID", "") or event.get("Unique-ID", "")
        tenant_id = event.get("variable_zenith_tenant_id", "") or ""
        pbx_id = event.get("variable_zenith_pbx_id", "") or ""
        agent_ext = event.get("variable_zenith_agent_extension", "") or ""

        if not call_id:
            return

        from src.audio.ingestor import audio_ingestor
        audio_ingestor.register_stream_metadata(call_id, tenant_id, pbx_id, agent_ext)

        if tenant_id:
            await create_call_record(tenant_id, call_id, pbx_id, agent_ext)

    async def _handle_channel_hangup(self, event: dict):
        call_id = event.get("Caller-Unique-ID", "") or event.get("Unique-ID", "")
        tenant_id = event.get("variable_zenith_tenant_id", "") or ""

        if not call_id:
            return

        if tenant_id:
            await finalize_call_record(tenant_id, call_id)

        from src.audio.ingestor import audio_ingestor
        chunks = audio_ingestor.buffers.pop(call_id, [])
        if not chunks:
            return

        by_channel: dict[str, bytearray] = defaultdict(bytearray)
        for chunk in chunks:
            by_channel[chunk.channel].extend(chunk.data)
        recordings = [{"channel": channel, "data": bytes(data)} for channel, data in by_channel.items()]
        await enqueue_recording_upload(tenant_id, call_id, recordings)

    async def _handle_manual_linkage(self, event: dict):
        from_user = event.get("Caller-Caller-ID-Number", "") or event.get("sip_from_user", "")
        sip_ip = self._extract_ip(event)
        channel_uuid = event.get("Unique-ID", "")

        if not from_user or not sip_ip:
            return

        from src.api.websockets import agent_assist_ws
        await agent_assist_ws.broadcast("manual_linkage", {
            "event": "manual_linkage_detected",
            "data": {
                "extension": from_user,
                "source_ip": sip_ip,
                "channel_uuid": channel_uuid,
            },
        })

    def _extract_ip(self, event: dict) -> str:
        sip_ip = event.get("sip_network_ip", "") or event.get("Caller-Network-Addr", "") or ""
        if not sip_ip:
            candidate = event.get("Caller-Source", "") or event.get("sip_via_host", "") or ""
            match = re.search(r"(\d+\.\d+\.\d+\.\d+)", candidate)
            if match:
                sip_ip = match.group(1)
        return sip_ip

    async def _cache_sip_mapping(self, extension: str, ip: str, event: dict):
        await event_bus.redis.setex(
            f"zenith:sip:ip_to_extension:{ip}", SIP_IP_KEY_TTL, extension
        )
        await event_bus.redis.setex(
            f"zenith:sip:extension_to_ip:{extension}", SIP_IP_KEY_TTL, ip
        )

    async def _remove_sip_mapping(self, extension: str):
        ip = await event_bus.redis.get(f"zenith:sip:extension_to_ip:{extension}")
        if ip:
            await event_bus.redis.delete(f"zenith:sip:ip_to_extension:{ip.decode()}")
        await event_bus.redis.delete(f"zenith:sip:extension_to_ip:{extension}")

    async def close(self):
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.connected = False


esl_client = ESLClient()
