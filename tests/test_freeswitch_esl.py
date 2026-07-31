import asyncio
import os

import pytest

from src.config import settings
from src.telephony.esl_client import ESLClient

LOCAL_TEST_PASSWORD = "local-test-secret"


class _FramingAuthESLServer:
    """Servidor asyncio local (127.0.0.1, porta efêmera) que reproduz o handshake
    ESL real: manda o greeting "auth/request" e espera receber exatamente
    "auth <senha>\\n\\n" antes de responder +OK. Usado para provar o framing
    do protocolo sem depender de FreeSWITCH de verdade."""

    def __init__(self, password: str):
        self._password = password
        self._server: asyncio.Server | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.received_auth_frame: bytes | None = None

    async def start(self) -> tuple[str, int]:
        self._server = await asyncio.start_server(self._handle_client, "127.0.0.1", 0)
        host, port = self._server.sockets[0].getsockname()[:2]
        return host, port

    async def stop(self):
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._writer = writer
        writer.write(b"Content-Type: auth/request\n\n")
        await writer.drain()

        self.received_auth_frame = await asyncio.wait_for(reader.readuntil(b"\n\n"), timeout=5.0)

        if self.received_auth_frame == f"auth {self._password}\n\n".encode():
            writer.write(b"Content-Type: command/reply\nReply-Text: +OK accepted\n\n")
        else:
            writer.write(b"Content-Type: command/reply\nReply-Text: -ERR invalid\n\n")
        await writer.drain()


class _StallingESLServer:
    """Servidor asyncio local que manda o greeting e nunca responde ao "auth",
    para provar que o cliente aplica timeout explícito em vez de travar."""

    def __init__(self):
        self._server: asyncio.Server | None = None
        self._client_tasks: set[asyncio.Task] = set()

    async def start(self) -> tuple[str, int]:
        self._server = await asyncio.start_server(self._handle_client, "127.0.0.1", 0)
        host, port = self._server.sockets[0].getsockname()[:2]
        return host, port

    async def stop(self):
        for task in self._client_tasks:
            task.cancel()
        if self._client_tasks:
            await asyncio.gather(*self._client_tasks, return_exceptions=True)
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        task = asyncio.current_task()
        self._client_tasks.add(task)
        try:
            writer.write(b"Content-Type: auth/request\n\n")
            await writer.drain()
            await asyncio.sleep(3600)  # propositalmente nunca responde ao auth
        finally:
            self._client_tasks.discard(task)
            writer.close()


@pytest.mark.asyncio
async def test_esl_connect_frames_auth_with_double_newline_and_reads_ok():
    # Arrange: servidor ESL local que exige receber "auth <senha>\n\n" exato
    fake_server = _FramingAuthESLServer(password=LOCAL_TEST_PASSWORD)
    host, port = await fake_server.start()
    client = ESLClient(host=host, port=port, password=LOCAL_TEST_PASSWORD)

    try:
        # Act: usa a API real do cliente (connect) contra o servidor local
        await asyncio.wait_for(client.connect(), timeout=5.0)

        # Assert: o servidor recebeu exatamente o frame "auth <senha>\n\n" e o
        # cliente marcou a conexão como autenticada após o +OK
        assert fake_server.received_auth_frame == f"auth {LOCAL_TEST_PASSWORD}\n\n".encode()
        assert client.connected is True
    finally:
        await client.close()
        await fake_server.stop()


@pytest.mark.asyncio
async def test_esl_connect_raises_timeout_when_server_never_replies_to_auth():
    # Arrange: servidor ESL local que manda o greeting e trava propositalmente
    stalling_server = _StallingESLServer()
    host, port = await stalling_server.start()
    client = ESLClient(host=host, port=port, password=LOCAL_TEST_PASSWORD)

    try:
        # Act / Assert: timeout explícito de teste (6s) só como rede de segurança
        # acima do timeout interno de leitura do cliente (3s em esl_client.py)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.connect(), timeout=6.0)
    finally:
        await client.close()
        await stalling_server.stop()


@pytest.mark.asyncio
async def test_esl_connection_real_freeswitch():
    # Arrange: sem rede externa por padrão — só roda contra FreeSWITCH real
    # se FREESWITCH_ESL_INTEGRATION=1 for setado explicitamente
    if os.environ.get("FREESWITCH_ESL_INTEGRATION") != "1":
        pytest.skip(
            "FREESWITCH_ESL_INTEGRATION != 1: integração real com FreeSWITCH "
            "desabilitada por padrão para não depender de rede externa"
        )

    client = ESLClient(
        host=settings.FREESWITCH_ESL_HOST,
        port=settings.FREESWITCH_ESL_PORT,
        password=settings.FREESWITCH_ESL_PASSWORD,
    )

    try:
        # Act
        await asyncio.wait_for(client.connect(), timeout=8.0)

        # Assert
        assert client.connected is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_esl_status_real_freeswitch():
    # Arrange: sem rede externa por padrão — só roda contra FreeSWITCH real
    # se FREESWITCH_ESL_INTEGRATION=1 for setado explicitamente
    if os.environ.get("FREESWITCH_ESL_INTEGRATION") != "1":
        pytest.skip(
            "FREESWITCH_ESL_INTEGRATION != 1: integração real com FreeSWITCH "
            "desabilitada por padrão para não depender de rede externa"
        )

    client = ESLClient(
        host=settings.FREESWITCH_ESL_HOST,
        port=settings.FREESWITCH_ESL_PORT,
        password=settings.FREESWITCH_ESL_PASSWORD,
    )
    await asyncio.wait_for(client.connect(), timeout=8.0)

    try:
        # Act
        response = await asyncio.wait_for(client.send_api("status"), timeout=8.0)

        # Assert
        assert "+OK" in response or "UP" in response or "Session" in response
    finally:
        await client.close()
