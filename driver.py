import asyncio
import logging

import uvloop

from autobrowser.driver import Driver

logger = logging.getLogger("autobrowser")

if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.setLevel(logging.DEBUG)
    loop = asyncio.get_event_loop()
    driver = Driver(loop=loop)
    loop.run_until_complete(driver.pubsub_loop())
