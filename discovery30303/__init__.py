import asyncio
import contextlib
import logging
import socket
import time

_LOGGER = logging.getLogger(__name__)

__version__ = "0.1.1"


MAX_UPDATES_WITHOUT_RESPONSE = 4


def normalize_mac(mac: str) -> str:
    return ":".join([i.zfill(2) for i in mac.replace("-", ":").split(":")])


class Discovery30303(asyncio.DatagramProtocol):
    def __init__(self, destination, on_response):
        self.transport = None
        self.destination = destination
        self.on_response = on_response

    def datagram_received(self, data, addr) -> None:
        """Trigger on_response."""
        self.on_response(data, addr)

    def error_received(self, ex):
        """Handle error."""
        _LOGGER.error("Discovery30303 error: %s", ex)

    def connection_lost(self, ex):
        pass


class AIODiscovery30303:
    """A 30303 discovery scanner."""

    DISCOVERY_PORT = 30303
    BROADCAST_FREQUENCY = 3
    RESPONSE_SIZE = 64
    DISCOVER_MESSAGE = b"Discovery: Who is out there?"
    BROADCAST_ADDRESS = "<broadcast>"

    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.found_devices = []

    def _create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with contextlib.suppress(Exception):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind(("", self.DISCOVERY_PORT))
        sock.setblocking(0)
        return sock

    def _destination_from_address(self, address):
        if address is None:
            address = self.BROADCAST_ADDRESS
        return (address, self.DISCOVERY_PORT)

    def _process_response(self, data, from_address, address, response_list):
        """Process a response.

        Returns True if processing should stop
        """
        if data is None:
            return
        if data == self.DISCOVER_MESSAGE:
            return
        data_split = data.decode("utf-8").split("\r\n")
        if len(data_split) < 3:
            return
        if from_address[0] in response_list:
            return
        response_list[from_address] = {
            "hostname": data_split[0].rstrip(),
            "ipaddr": from_address[0],
            "mac": normalize_mac(data_split[1].rstrip()),
            "model": data_split[2].split("\x00")[0].rstrip(),
        }
        return from_address[0] == address

    async def _async_run_scan(self, transport, destination, timeout, found_all_future):
        """Send the scans."""
        _LOGGER.debug("discover: %s => %s", destination, self.DISCOVER_MESSAGE)
        transport.sendto(self.DISCOVER_MESSAGE, destination)
        quit_time = time.monotonic() + timeout
        remain_time = timeout
        while True:
            time_out = min(remain_time, timeout / self.BROADCAST_FREQUENCY)
            if time_out <= 0:
                return
            try:
                await asyncio.wait_for(
                    asyncio.shield(found_all_future), timeout=time_out
                )
            except asyncio.TimeoutError:
                if time.monotonic() >= quit_time:
                    return
                # No response, send broadcast again in cast it got lost
                _LOGGER.debug("discover: %s => %s", destination, self.DISCOVER_MESSAGE)
                transport.sendto(self.DISCOVER_MESSAGE, destination)
            else:
                return  # found_all
            remain_time = quit_time - time.monotonic()

    async def async_scan(self, timeout=10, address=None):
        """Discover on port 30303."""
        sock = self._create_socket()
        destination = self._destination_from_address(address)
        found_all_future = asyncio.Future()
        response_list = {}

        def _on_response(data, addr):
            _LOGGER.debug("discover: %s <= %s", addr, data)
            if self._process_response(data, addr, address, response_list):
                found_all_future.set_result(True)

        transport, _ = await self.loop.create_datagram_endpoint(
            lambda: Discovery30303(
                destination=destination,
                on_response=_on_response,
            ),
            sock=sock,
        )
        try:
            await self._async_run_scan(
                transport, destination, timeout, found_all_future
            )
        finally:
            transport.close()

        self.found_devices = response_list.values()
        return list(self.found_devices)
