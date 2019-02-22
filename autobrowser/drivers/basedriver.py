import logging
from abc import ABC
from asyncio import AbstractEventLoop
from collections import Counter
from typing import Counter as CounterT, List, Optional

import aioredis
from aiohttp import ClientSession
from aioredis import Redis

from autobrowser.abcs import Driver
from autobrowser.automation import AutomationConfig, BrowserExitInfo, ShutdownCondition
from autobrowser.behaviors import RemoteBehaviorManager
from autobrowser.chrome_browser import Chrome
from autobrowser.util import Helper

__all__ = ["BaseDriver"]

logger = logging.getLogger("autobrowser")


class BaseDriver(Driver, ABC):
    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        """Create a new driver

        :param conf: The automation configuration object
        :param loop: The event loop to be used
        """
        self.conf: AutomationConfig = conf
        self.loop: AbstractEventLoop = Helper.ensure_loop(loop)
        self.did_init: bool = False
        self.shutdown_condition: ShutdownCondition = ShutdownCondition(loop=self.loop)
        self.session: ClientSession = Helper.create_aio_http_client_session(loop)
        self.behavior_manager: RemoteBehaviorManager = RemoteBehaviorManager(
            behavior_endpoint=self.conf.get("fetch_behavior_endpoint"),
            behavior_info_endpoint=self.conf.get("fetch_behavior_info_endpoint"),
            session=self.session,
        )
        self.redis: Redis = None
        self._class_name: str = self.__class__.__name__
        self._browser_exit_infos: List[BrowserExitInfo] = []

    async def init(self) -> None:
        """Initialize the driver."""
        logger.info(f"{self._class_name}[init]: connecting to redis")
        self.did_init = True
        redis_url = self.conf.get("redis_url")
        self.redis = await aioredis.create_redis_pool(
            redis_url, loop=self.loop, encoding="utf-8"
        )
        logger.info(f"{self._class_name}[init]: connected to redis")

    async def clean_up(self) -> None:
        """Performs any necessary cleanup Close all dependant resources.

        This method should be called from subclasses shutdown.
        """
        if self.redis is None:
            return
        logger.info(f"{self._class_name}[clean_up]: closing redis connection")
        self.redis.close()
        await self.redis.wait_closed()
        self.redis = None
        self.behavior_manager = None
        logger.info(f"{self._class_name}[clean_up]: closed redis connection")

    async def run(self) -> int:
        """Start running the driver.

        Subclasses should not override this method rather override
        one of the lifecycle methods

        Lifecycle methods called:
          - await init
          - await shutdown_condition
          - await shutdown
        """
        logger.info(f"{self._class_name}[run]: running")
        if not self.did_init:
            await self.init()
        logger.info(f"{self._class_name}[run]: waiting for shutdown")
        await self.shutdown_condition
        logger.info(f"{self._class_name}[run]: shutdown condition met")
        return await self.shutdown()

    async def gracefully_shutdown_browser(self, browser: Chrome) -> None:
        """Gracefully shutdowns a browser and adds its exit info to
        the list of browser exit infos.

        :param browser: The browser to gracefully shutdown
        """
        browser.remove_all_listeners()
        future_exit_info = self.loop.create_future()
        browser.once(
            Chrome.Events.Exiting, lambda info: future_exit_info.set_result(info)
        )
        await browser.shutdown_gracefully()
        self._browser_exit_infos.append(await future_exit_info)

    def determine_exit_code(self) -> int:
        """Determines the exit code based on the exit info's of the browsers.

        If the shutdown condition was met by signal the return value is 1.

        If there were no browser exit info's the return value is 0.

        If there was one browser exit info then the return value is
        the results of calling `BrowserExitInfo.exit_reason_code()`

        Otherwise the return value is `BrowserExitInfo.exit_reason_code()`
        that was seen the most times.

        :return: An exit code based on the exit info's of the browsers
        """
        if self.shutdown_condition.shutdown_from_signal:
            logger.info(
                f"{self._class_name}[determine_exit_code]: exit code 1, shutdown from signal"
            )
            return 1
        beis_len = len(self._browser_exit_infos)
        if beis_len == 0:
            logger.info(
                f"{self._class_name}[determine_exit_code]: exit code 0, no browser exit info"
            )
            return 0
        elif beis_len == 1:
            logger.info(
                f"{self._class_name}[determine_exit_code]: 1 browser exit info, using its exit code"
            )
            return self._browser_exit_infos[0].exit_reason_code()
        logger.info(
            f"{self._class_name}[determine_exit_code]: {beis_len} browser exit infos, using their exit code"
        )
        browser_exit_counter: CounterT[int] = Counter()
        for bei in self._browser_exit_infos:
            browser_exit_counter[bei.exit_reason_code()] += 1
        exit_code, count = max(
            browser_exit_counter.items(), key=lambda reason_count: reason_count[1]
        )
        return exit_code

    def initiate_shutdown(self) -> None:
        """Initiate the complete shutdown of the driver (running automation).

        This method should be used to shutdown (stop) the driver from running
        rather than calling :func:`~basedriver.Driver.shutdown` directly
        """
        self.shutdown_condition.initiate_shutdown()
