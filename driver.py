import asyncio
import logging
import os

import uvloop

from autobrowser.automation.details import AutomationConfig
from autobrowser.driver import SingleBrowserDriver, MultiBrowserDriver

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
logger.setLevel(logging.DEBUG)


async def run_driver():
    loop = asyncio.get_event_loop()
    if os.environ.get("BROWSER_HOST"):
        logger.info("run_driver: using SingleBrowserDriver")
        driver = SingleBrowserDriver(
            conf=AutomationConfig(tab_type="CrawlerTab"), loop=loop
        )
    else:
        logger.info("run_driver: using Driver")
        driver = MultiBrowserDriver(conf=AutomationConfig(), loop=loop)
    await driver.run()


if __name__ == "__main__":
    aiorun(run_driver())
