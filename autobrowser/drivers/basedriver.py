import asyncio
import logging
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop
from collections import Counter
from typing import List, Optional

import aioredis
from aioredis import Redis

from autobrowser.automation import (
    AutomationConfig,
    BrowserExitInfo,
    ShutdownCondition,
)
from autobrowser.browser import Browser

__all__ = ["Driver"]

logger = logging.getLogger("autobrowser")


class Driver(ABC):
    """Abstract base driver class that defines a common interface for all
    driver implementations and is responsible for managing the redis connection.
    """

    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        """

        :param conf: The automation configuration object
        :param loop: The event loop to be used
        """
        self.conf: AutomationConfig = conf
        self.loop: AbstractEventLoop = loop if loop is not None else asyncio.get_event_loop()
        self.did_init: bool = False
        self.shutdown_condition: ShutdownCondition = ShutdownCondition(loop=self.loop)
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
        """Performs any necessary cleanup Close all dependant resources"""
        if self.redis is None:
            return
        logger.info(f"{self._class_name}[clean_up]: closing redis connection")
        self.redis.close()
        await self.redis.wait_closed()
        self.redis = None
        logger.info(f"{self._class_name}[clean_up]: closed redis connection")

    async def run(self) -> int:
        """Start the driver"""
        logger.info(f"{self._class_name}[run]: running")
        if not self.did_init:
            await self.init()
        logger.info(f"{self._class_name}[run]: waiting for shutdown")
        await self.shutdown_condition
        logger.info(f"{self._class_name}[run]: shutdown condition met")
        return await self.shutdown()

    async def gracefully_shutdown_browser(self, browser: Browser) -> None:
        browser.remove_all_listeners()
        future_exit_info = self.loop.create_future()
        browser.once(
            Browser.Events.Exiting, lambda info: future_exit_info.set_result(info)
        )
        await browser.shutdown_gracefully()
        self._browser_exit_infos.append(await future_exit_info)

    def determine_exit_code(self) -> int:
        if self.shutdown_condition.shutdown_from_signal:
            return 1
        beis_len = len(self._browser_exit_infos)
        if beis_len == 0:
            return 0
        elif beis_len == 1:
            return self._browser_exit_infos[0].exit_reason_code()
        browser_exit_counter = Counter()
        for bei in self._browser_exit_infos:
            browser_exit_counter[bei.exit_reason_code()] += 1
        exit_code, count = max(
            browser_exit_counter.items(), key=lambda reason_count: reason_count[1]
        )
        return exit_code

    @abstractmethod
    async def shutdown(self) -> int:
        """Stop the driver from running and perform
        any necessary cleanup required before exiting"""
        pass

    @abstractmethod
    def on_browser_exit(self, info: BrowserExitInfo) -> None:
        """Method used as the listener for when a browser
        exits abnormally

        :param info: Automation info uniquely identifying
        browser that exited
        :return:
        """
        pass
