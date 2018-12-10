# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import socket
import ujson
from asyncio import AbstractEventLoop, Task, CancelledError
from typing import Dict

import aioredis
import attr
from aioredis import Redis, Channel

from .browser import Browser, DynamicBrowser
from .automation import AutomationInfo, BrowserRequests, ShutdownCondition

__all__ = ["Driver", "SingleBrowserDriver", "run_driver"]

logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True, cmp=False)
class Driver(object):
    loop: AbstractEventLoop = attr.ib(default=None)
    browsers: Dict[str, DynamicBrowser] = attr.ib(init=False, factory=dict)
    redis: Redis = attr.ib(init=False, default=None)
    ae_channel: Channel = attr.ib(init=False, default=None)
    pubsub_task: Task = attr.ib(init=False, default=None)
    shutdown_condition: ShutdownCondition = attr.ib(init=False, default=None)

    async def get_auto_event_channel(self) -> Channel:
        channels = await self.redis.subscribe("auto-event")
        return channels[0]

    async def init(self) -> None:
        if self.loop is None:
            self.loop = asyncio.get_event_loop()
        self.redis = await aioredis.create_redis(
            "redis://redis", loop=self.loop, encoding="utf-8"
        )
        self.ae_channel = await self.get_auto_event_channel()
        self.shutdown_condition = ShutdownCondition(self.loop)
        self.pubsub_task = self.loop.create_task(self.pubsub_loop())

    async def run(self) -> None:
        logger.info("Driver.run")
        await self.init()
        logger.info("Driver waiting for shutdown")
        await self.shutdown_condition
        self.pubsub_task.cancel()
        try:
            await self.pubsub_task
        except CancelledError:
            pass
        self.ae_channel.close()
        for browser in self.browsers.values():
            await browser.shutdown_gracefully()
        self.browsers.clear()
        self.redis.close()
        await self.redis.wait_closed()

    async def pubsub_loop(self) -> None:
        while await self.ae_channel.wait_message():
            msg = await self.ae_channel.get(encoding="utf-8", decoder=ujson.loads)
            logger.debug(f"pubsub_loop got message {msg}")
            if msg["type"] == "start":
                await self.add_browser(msg["reqid"])
            elif msg["type"] == "stop":
                await self.remove_browser(msg["reqid"])

    async def add_browser(self, reqid) -> None:
        logger.debug("Start Automating Browser: " + reqid)
        browser = self.browsers.get(reqid)
        if not browser:
            browser = DynamicBrowser(
                BrowserRequests(api_host="http://shepherd:9020"),
                loop=self.loop,
                redis=self.redis,
                sd_condition=self.shutdown_condition,
            )

            await browser.init(AutomationInfo(reqid=reqid))
            self.browsers[reqid] = browser

    async def remove_browser(self, reqid) -> None:
        logger.debug("Stop Automating Browser: " + reqid)
        browser = self.browsers.get(reqid)
        if not browser:
            return

        await browser.close()
        del self.browsers[reqid]
        # browser.remove_listener('browser_removed', self.remove_browser)


@attr.dataclass(slots=True, cmp=False)
class SingleBrowserDriver(object):
    loop: AbstractEventLoop = attr.ib(default=None)
    redis: Redis = attr.ib(init=False, default=None)
    shutdown_condition: ShutdownCondition = attr.ib(init=False, default=None)
    browser: Browser = attr.ib(init=False, default=None)

    async def run(self) -> None:
        if self.loop is None:
            self.loop = asyncio.get_event_loop()
        logger.info("SingleBrowserDriver[run]: started")
        redis_url = os.environ.get("REDIS_URL", "redis://localhost")
        print("REDIS", redis_url)
        self.redis = await aioredis.create_redis(
            redis_url, loop=self.loop, encoding="utf-8"
        )
        self.shutdown_condition = ShutdownCondition(self.loop)

        logger.debug("SingleBrowserDriver[run]: connecting to Auto-Browser")

        browser = Browser(
            BrowserRequests(),
            loop=self.loop,
            redis=self.redis,
            sd_condition=self.shutdown_condition,
        )

        await browser.init(
            AutomationInfo(
                tab_type="CrawlerTab",
                autoid=os.environ.get("AUTO_ID"),
                ip=socket.gethostbyname(os.environ.get("BROWSER_HOST"))
            )
        )
        logger.info("SingleBrowserDriver[run]: waiting for shutdown")
        await self.shutdown_condition
        await browser.shutdown_gracefully()
        self.redis.close()
        await self.redis.wait_closed()


async def run_driver():
    loop = asyncio.get_event_loop()
    if os.environ.get("BROWSER_HOST"):
        logger.info("run_driver: using SingleBrowserDriver")
        cls = SingleBrowserDriver(loop=loop)
    else:
        logger.info("run_driver: using Driver")
        cls = Driver(loop=loop)

    await cls.run()
