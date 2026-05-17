import asyncio
from src.config import settings


class ESLClient:
    def __init__(self, host: str = settings.FREESWITCH_ESL_HOST, port: int = settings.FREESWITCH_ESL_PORT, password: str = settings.FREESWITCH_ESL_PASSWORD):
        self.host = host
        self.port = port
        self.password = password
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.connected = False
        self.uuid_map: dict[str, dict[str, str]] = {}

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

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.connected = False


esl_client = ESLClient()
