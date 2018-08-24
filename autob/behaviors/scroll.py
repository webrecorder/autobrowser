# -*- coding: utf-8 -*-
import os
import asyncio
import aiofiles
from .basebavior import Behavior


class ControlledScrollBehavior(Behavior):
    """The scroll performed by this behavior is controlled by a flag contained in page itself."""

    SCROLL_COND = "window.scrollY + window.innerHeight < Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
    SCROLL_INC = "window.scrollBy(0, 80)"
    SCROLL_SPEED = 0.2

    async def run(self):
        while True:
            is_paused = await self.tab.evaluate_in_page("window.__wr_scroll_paused")
            self.paused = bool(is_paused["result"].get("value"))

            if self.paused:
                print("Scroll Paused")
                await asyncio.sleep(1.0)
                continue

            should_scroll = await self.tab.evaluate_in_page(self.SCROLL_COND)

            if not should_scroll["result"]["value"]:
                break

            await self.tab.evaluate_in_page(self.SCROLL_INC)

            await asyncio.sleep(self.SCROLL_SPEED)


class AutoScrollBehavior(Behavior):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._js: str = None

    async def _load_resources(self):
        async with aiofiles.open(
            f"{os.path.dirname(__file__)}/behaviorjs/autoscroll.js", "r"
        ) as iin:
            self._js = await iin.read()

    async def run(self):
        if self._js is None:
            await self._load_resources()
        await self.tab.evaluate_in_page(self._js)
