# -*- coding: utf-8 -*-
import logging

from .basebehavior import JSBasedBehavior

__all__ = ["TimelineFeedBehavior"]

logger = logging.getLogger("autobrowser")


class TimelineFeedBehavior(JSBasedBehavior):
    async def run(self) -> None:
        logger.debug(f"TimelineFeedBehavior.run")
        if not self._did_init:
            await self.tab.evaluate_in_page(self._init_inject)
            self._did_init = True
        done = await self.tab.evaluate_in_page("window.$WRIteratorHandler$()")
        logger.debug(f"TimelineFeedBehavior done ? {done}")
        if done.get("result").get("value"):
            self.tab.pause_behaviors()
