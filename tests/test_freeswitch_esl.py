import pytest
import asyncio
from src.config import settings


@pytest.mark.asyncio
async def test_esl_connection():
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(settings.FREESWITCH_ESL_HOST, settings.FREESWITCH_ESL_PORT),
            timeout=5.0,
        )
        auth_cmd = f"auth {settings.FREESWITCH_ESL_PASSWORD}\n\n"
        writer.write(auth_cmd.encode())
        await writer.drain()
        response = await asyncio.wait_for(reader.read(4096), timeout=3.0)
        assert b"OK" in response or b"+OK" in response
        writer.close()
        await writer.wait_closed()
    except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
        pytest.skip("FreeSWITCH ESL not available in this test environment")


@pytest.mark.asyncio
async def test_esl_status():
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(settings.FREESWITCH_ESL_HOST, settings.FREESWITCH_ESL_PORT),
            timeout=5.0,
        )
        auth_cmd = f"auth {settings.FREESWITCH_ESL_PASSWORD}\n\n"
        writer.write(auth_cmd.encode())
        await writer.drain()
        await asyncio.wait_for(reader.read(4096), timeout=3.0)

        status_cmd = "api status\n\n"
        writer.write(status_cmd.encode())
        await writer.drain()
        response = await asyncio.wait_for(reader.read(8192), timeout=3.0)
        assert b"UP" in response or b"Session" in response
        writer.close()
        await writer.wait_closed()
    except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
        pytest.skip("FreeSWITCH ESL not available")
