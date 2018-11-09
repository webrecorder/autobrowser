import asyncio
import logging
import os

import uvloop

from autobrowser.driver import Driver, SingleBrowserDriver

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

try:
    from asyncio.runners import run as aiorun
except ImportError:

    def aiorun(coro):
        _loop = asyncio.get_event_loop()
        try:
            return _loop.run_until_complete(coro)
        finally:
            _loop.close()


logger = logging.getLogger("autobrowser")


async def run_driver():
    if os.environ.get('BROWSER_HOST'):
        cls = SingleBrowserDriver
    else:
        cls = Driver

    await cls(loop=asyncio.get_event_loop()).run()


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    aiorun(run_driver())
