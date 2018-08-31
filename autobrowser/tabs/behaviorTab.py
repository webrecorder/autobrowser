# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Optional, Dict, Any

from autobrowser import AutoScrollBehavior
from .basetab import BaseAutoTab

__all__ = ["BehaviorTab"]

logger = logging.getLogger("autobrowser")


class BehaviorTab(BaseAutoTab):
    async def init(self) -> None:
        if self._running:
            return
        await super().init()
        asb = AutoScrollBehavior(tab=self)
        if asb.has_resources:
            await asb.load_resources()
        self.add_behavior(asb)

        self.all_behaviors = asyncio.ensure_future(
            self._behavior_loop(), loop=asyncio.get_event_loop()
        )

    async def close(self) -> None:
        if self.all_behaviors:
            self.all_behaviors.cancel()
            self.all_behaviors = None
        await super().close()

    async def evaluate_in_page(self, js_string: str):
        return await self.client.Runtime.evaluate(
            js_string, userGesture=True, awaitPromise=True, includeCommandLineAPI=True
        )

    async def goto(self, url: str, options: Optional[Dict] = None, **kwargs: Any):
        pass

    @classmethod
    def create(cls, *args, **kwargs) -> "BehaviorTab":
        return cls(*args, **kwargs)

    async def _behavior_loop(self):
        logger.debug("BehaviorTab._behavior_loop running")
        while not self.behaviors_paused:
            for behavior in self.behaviors:
                await behavior.run()
            await asyncio.sleep(1)

    def __repr__(self):
        return "BehaviorTab"