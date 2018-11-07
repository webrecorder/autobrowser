import asyncio
import logging

import uvloop

from autobrowser.driver import Driver

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

if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    aiorun(Driver().run())
