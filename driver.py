import asyncio
import logging
import os

from autobrowser import (
    run_automation,
    SingleBrowserDriver,
    MultiBrowserDriver,
    build_automation_config,
)

logger = logging.getLogger("autobrowser")
logger.setLevel(logging.DEBUG)


async def run_driver() -> int:
    loop = asyncio.get_event_loop()
    if os.environ.get("BROWSER_HOST"):
        logger.info("run_driver: using SingleBrowserDriver")
        driver = SingleBrowserDriver(conf=build_automation_config(), loop=loop)
    else:
        logger.info("run_driver: using MultiBrowserDriver")
        driver = MultiBrowserDriver(conf=build_automation_config(), loop=loop)
    return await driver.run()


if __name__ == "__main__":
    run_automation(run_driver())
