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


logger = logging.getLogger('autobrowser')
logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler(sys.stdout))


async def run_driver():
    loop = asyncio.get_event_loop()
    if os.environ.get('BROWSER_HOST'):
        logger.info('run_driver: using SingleBrowserDriver')
        cls = SingleBrowserDriver(loop=loop)
    else:
        logger.info('run_driver: using Driver')
        cls = Driver(loop=loop)

    await cls.run()


if __name__ == "__main__":
    aiorun(run_driver())
