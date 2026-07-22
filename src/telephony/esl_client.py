import asyncio
import json
import logging
import re
from collections import defaultdict
from src.config import settings
from src.events.redis_streams import event_bus
from src.services.calls import create_call_record, finalize_call_record
from src.workers.audio_uploader import enqueue_recording_upload

logger = logging.getLogger(__name__)

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
        # Conexão ESL dedicada a api/bgapi, separada da conexão de eventos: as duas
        # compartilhando o mesmo socket causava corrida de leitura entre o loop de
        # eventos e a resposta de um comando disparado de dentro de um handler de
        # evento (ex: uuid_audio_stream em _handle_channel_answer) — a resposta do
        # comando podia se misturar com o próximo evento e se perder.
        self._cmd_reader: asyncio.StreamReader | None = None
        self._cmd_writer: asyncio.StreamWriter | None = None
        self._cmd_lock = asyncio.Lock()

    async def connect(self):
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=5.0
        )
        # FreeSWITCH manda "Content-Type: auth/request\n\n" assim que a conexão abre,
        # antes de qualquer comando nosso — precisa consumir essa saudação primeiro,
        # senão ela é lida como se fosse a resposta do nosso "auth".
        await asyncio.wait_for(self.reader.read(4096), timeout=3.0)

        auth = f"auth {self.password}\n\n"
        self.writer.write(auth.encode())
        await self.writer.drain()
        response = await asyncio.wait_for(self.reader.read(4096), timeout=3.0)
        if b"+OK" not in response and b"OK" not in response:
            raise ConnectionError(f"ESL auth failed: {response}")

        self.writer.write(b"events json CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP SOFIA_REGISTER SOFIA_UNREGISTER\n\n")
        await self.writer.drain()
        self.connected = True

    async def _connect_command(self):
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=5.0
        )
        await asyncio.wait_for(reader.read(4096), timeout=3.0)

        writer.write(f"auth {self.password}\n\n".encode())
        await writer.drain()
        response = await asyncio.wait_for(reader.read(4096), timeout=3.0)
        if b"+OK" not in response and b"OK" not in response:
            raise ConnectionError(f"ESL command auth failed: {response}")
        self._cmd_reader, self._cmd_writer = reader, writer

    async def _send_command(self, prefix: str, command: str, timeout: float) -> str:
        async with self._cmd_lock:
            if self._cmd_writer is None or self._cmd_writer.is_closing():
                await self._connect_command()
            try:
                self._cmd_writer.write(f"{prefix} {command}\n\n".encode())
                await self._cmd_writer.drain()
                response = await asyncio.wait_for(self._cmd_reader.read(8192), timeout=timeout)
                return response.decode(errors="replace")
            except (ConnectionError, asyncio.TimeoutError, OSError):
                self._cmd_writer = None
                raise

    async def send_api(self, command: str) -> str:
        return await self._send_command("api", command, timeout=10.0)

    async def send_bgapi(self, command: str) -> str:
        return await self._send_command("bgapi", command, timeout=5.0)

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
        buffer = b""
        while self._running and self.connected:
            # FreeSWITCH não manda heartbeat em conexão ESL ociosa: um timeout curto aqui
            # derruba e reconecta a cada janela sem chamada, criando um gap onde eventos
            # reais (CHANNEL_ANSWER) podem chegar e ser perdidos. Desconexão real já é
            # detectada abaixo por `read()` retornar vazio (EOF), sem precisar de timeout.
            chunk = await asyncio.wait_for(self.reader.read(65536), timeout=300.0)
            if not chunk:
                raise ConnectionError("ESL connection closed")
            buffer += chunk
            while True:
                # Protocolo ESL: bloco de headers (linha a linha) terminado por uma linha
                # em branco, seguido do corpo com exatamente Content-Length bytes — não
                # dá pra usar "\n\n" como delimitador do corpo (o JSON do evento pode
                # conter sequências que colidem com isso), tem que respeitar o tamanho.
                header_end = buffer.find(b"\n\n")
                if header_end == -1:
                    break
                header_block = buffer[:header_end].decode(errors="replace")
                content_length = 0
                for line in header_block.split("\n"):
                    if line.lower().startswith("content-length:"):
                        content_length = int(line.split(":", 1)[1].strip())
                        break
                body_start = header_end + 2
                if len(buffer) < body_start + content_length:
                    break
                body = buffer[body_start:body_start + content_length]
                buffer = buffer[body_start + content_length:]
                await self._process_event(body.decode(errors="replace"))

    async def _process_event(self, raw: str):
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            logger.info("Non-JSON payload on ESL stream (%d bytes): %r", len(raw), raw[:200])
            return

        event_name = event.get("Event-Name", "")
        logger.info("ESL event received: %s", event_name)
        try:
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
        except asyncio.CancelledError:
            raise
        except Exception:
            call_id = event.get("Caller-Unique-ID", "") or event.get("Unique-ID", "")
            logger.exception("Failed handling %s for call_id=%s", event_name, call_id)

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
        logger.info(
            "CHANNEL_ANSWER call_id=%s tenant_id=%r pbx_id=%r agent_ext=%r dest=%r",
            call_id, tenant_id, pbx_id, agent_ext, event.get("Caller-Destination-Number", ""),
        )

        if not call_id:
            return

        from src.audio.ingestor import audio_ingestor
        audio_ingestor.register_stream_metadata(call_id, tenant_id, pbx_id, agent_ext)

        if tenant_id:
            logger.info("create_call_record starting for call_id=%s", call_id)
            try:
                await create_call_record(tenant_id, call_id, pbx_id, agent_ext)
                logger.info("create_call_record finished for call_id=%s", call_id)
            except Exception:
                logger.exception("create_call_record raised for call_id=%s", call_id)
            await self._start_audio_capture(call_id)

    async def _start_audio_capture(self, call_id: str):
        ws_url = f"ws://{settings.AUDIO_STREAM_CALLBACK_HOST}/audio-stream/{call_id}"
        metadata = json.dumps({"call_id": call_id})
        command = f"uuid_audio_stream {call_id} start {ws_url} stereo 8k {metadata}"
        try:
            response = await self.send_bgapi(command)
        except (ConnectionError, asyncio.TimeoutError, OSError) as e:
            logger.warning("uuid_audio_stream dispatch failed for call_id=%s: %s", call_id, e)
            return
        if "-ERR" in response or "+OK" not in response:
            logger.warning("uuid_audio_stream rejected for call_id=%s: %s", call_id, response.strip())

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
        if self._cmd_writer:
            self._cmd_writer.close()
            await self._cmd_writer.wait_closed()
        self.connected = False


esl_client = ESLClient()
