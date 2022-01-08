import asyncio
import logging
import pprint

from discovery30303 import AIODiscovery30303

logging.basicConfig(level=logging.DEBUG)


async def go():
    scanner = AIODiscovery30303()
    pprint.pprint(await scanner.async_scan())


asyncio.run(go())
