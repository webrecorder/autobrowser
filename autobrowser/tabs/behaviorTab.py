# -*- coding: utf-8 -*-
import asyncio
import logging

from autobrowser.behaviors.behavior_manager import BehaviorManager
from .basetab import BaseAutoTab

__all__ = ["BehaviorTab"]

logger = logging.getLogger("autobrowser")


class BehaviorTab(BaseAutoTab):
    async def init(self) -> None:
        if self._running:
            return
        await super().init()
        behavior = BehaviorManager.behavior_for_url(self.tab_data.get("url"), self)
        self.add_behavior(behavior)
        self.all_behaviors = self._loop.create_task(self._behavior_loop())

    async def close(self) -> None:
        logger.info(f"BehaviorTab[close]: closing")
        if self.all_behaviors:
            self.all_behaviors.cancel()
            self.all_behaviors = None
        await super().close()

    @classmethod
    def create(cls, *args, **kwargs) -> "BehaviorTab":
        return cls(*args, **kwargs)

    async def _behavior_loop(self) -> None:
        logger.info("BehaviorTab[_behavior_loop]: started")
        while not self.behaviors_paused:
            for behavior in self.behaviors:
                await behavior.run()
            await asyncio.sleep(1)
