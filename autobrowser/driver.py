# -*- coding: utf-8 -*-
import asyncio
import logging
import signal
import ujson
from asyncio import AbstractEventLoop, Task, Future, CancelledError
from typing import Dict

import aioredis
import attr
from aioredis import Redis, Channel

from .basebrowser import BaseAutoBrowser

__all__ = ["Driver"]


logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True, cmp=False)
class Driver(object):
    loop: AbstractEventLoop = attr.ib(factory=asyncio.get_event_loop)
    browsers: Dict[str, BaseAutoBrowser] = attr.ib(init=False, factory=dict)
    redis: Redis = attr.ib(init=False, default=None)
    ae_channel: Channel = attr.ib(init=False, default=None)
    pubsub_task: Task = attr.ib(init=False, default=None)
    shutdown_sig_future: Future = attr.ib(init=False, default=None)

    def sigterm_handler(self) -> None:
        self.shutdown_sig_future.set_result(True)

    async def get_auto_event_channel(self) -> Channel:
        channels = await self.redis.subscribe("auto-event")
        return channels[0]

    async def init(self) -> None:
        self.redis = await aioredis.create_redis(
            "redis://redis", loop=self.loop, encoding="utf-8"
        )
        self.ae_channel = await self.get_auto_event_channel()
        self.shutdown_sig_future = self.loop.create_future()
        self.loop.add_signal_handler(signal.SIGTERM, self.sigterm_handler)
        self.pubsub_task = self.loop.create_task(self.pubsub_loop())

    async def run(self) -> None:
        await self.init()
        await self.shutdown_sig_future
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
            browser = BaseAutoBrowser(
                api_host="http://shepherd:9020",
                autoid=reqid,
                tab_class="BehaviorTab",
                loop=self.loop,
                redis=self.redis,
            )

            await browser.init(reqid)
            # browser.on('browser_removed', self.remove_browser)

            self.browsers[reqid] = browser

    async def remove_browser(self, reqid) -> None:
        logger.debug("Stop Automating Browser: " + reqid)
        browser = self.browsers.get(reqid)
        if not browser:
            return

        await browser.close()
        del self.browsers[reqid]
        # browser.remove_listener('browser_removed', self.remove_browser)
