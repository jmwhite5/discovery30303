import asyncio
import contextlib
import pprint
from unittest.mock import MagicMock, patch

import pytest

from discovery30303 import AIODiscovery30303, Discovery30303


@pytest.fixture
async def mock_discovery_aio_protocol():
    """Fixture to mock an asyncio connection."""
    loop = asyncio.get_running_loop()
    future = asyncio.Future()

    async def _wait_for_connection():
        transport, protocol = await future
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return transport, protocol

    async def _mock_create_datagram_endpoint(func, sock=None):
        protocol: Discovery30303 = func()
        transport = MagicMock()
        protocol.connection_made(transport)
        with contextlib.suppress(asyncio.InvalidStateError):
            future.set_result((transport, protocol))
        return transport, protocol

    with patch.object(loop, "create_datagram_endpoint", _mock_create_datagram_endpoint):
        yield _wait_for_connection


@pytest.mark.asyncio
async def test_async_scanner_specific_address(mock_discovery_aio_protocol):
    """Test scanner with a specific address."""
    scanner = AIODiscovery30303()

    task = asyncio.ensure_future(
        scanner.async_scan(timeout=10, address="192.168.213.252")
    )
    transport, protocol = await mock_discovery_aio_protocol()
    protocol.datagram_received(
        b"192.168.213.252,B4E842E10588,AK001-ZJ2145", ("192.168.213.252", 48899)
    )
    data = await task
    pprint.pprint(data)
