# -*- coding: utf-8 -*-
import asyncio
from asyncio import AbstractEventLoop
import logging
import ujson as json
from typing import Dict, Optional

import aioredis
from aioredis import Redis

from .basebrowser import BaseAutoBrowser

__all__ = ["Driver"]


logger = logging.getLogger("autobrowser")


class Driver(object):
    def __init__(self, loop: Optional[AbstractEventLoop] = None) -> None:
        self.browsers: Dict[str, BaseAutoBrowser] = {}
        self.redis: Redis = None
        self.loop = loop if loop is not None else asyncio.get_event_loop()

    async def pubsub_loop(self) -> None:
        self.redis = await aioredis.create_redis("redis://redis", loop=self.loop)

        channels = await self.redis.subscribe("auto-event")

        while channels[0].is_active:
            msg = await channels[0].get(encoding="utf-8")
            msg = json.loads(msg)
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
                reqid=reqid,
                tab_class="BehaviorTab",
                loop=self.loop,
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
