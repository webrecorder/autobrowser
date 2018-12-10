import asyncio
import logging

import uvloop

from autobrowser.driver import run_driver

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


logger = logging.getLogger('autobrowser')
logger.setLevel(logging.DEBUG)

if __name__ == "__main__":
    aiorun(run_driver())
