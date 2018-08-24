# -*- coding: utf-8 -*-
import asyncio
import logging

import aioredis
import ujson as json

from .basebrowser import BaseAutoBrowser
from .tabs import CripyAutoTab

logger = logging.getLogger(__file__)


class Driver(object):
    def __init__(self, loop=None):
        self.browsers = {}
        self.redis = None
        self.loop = loop if loop is not None else asyncio.get_event_loop()

    async def pubsub_loop(self):
        self.redis = await aioredis.create_redis("redis://redis", loop=self.loop)

        channels = await self.redis.subscribe("auto-event")

        while channels[0].is_active:
            msg = await channels[0].get(encoding="utf-8")
            msg = json.loads(msg)

            if msg["type"] == "start":
                await self.add_browser(msg["reqid"])

            elif msg["type"] == "stop":
                await self.remove_browser(msg["reqid"])

    async def add_browser(self, reqid):
        logger.debug("Start Automating Browser: " + reqid)
        browser = self.browsers.get(reqid)
        if not browser:
            browser = BaseAutoBrowser(
                api_host="http://shepherd:9020", reqid=reqid, tab_class=CripyAutoTab
            )

            await browser.init(reqid)

            self.browsers[reqid] = browser

    async def remove_browser(self, reqid):
        logger.debug("Stop Automating Browser: " + reqid)
        browser = self.browsers.get(reqid)
        if not browser:
            return

        await browser.close()
        del self.browsers[reqid]
