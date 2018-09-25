# -*- coding: utf-8 -*-
import logging

from .basebehavior import JSBasedBehavior

__all__ = ["TimelineFeedBehavior"]

logger = logging.getLogger("autobrowser")


class TimelineFeedBehavior(JSBasedBehavior):
    """Behavior for iterating over timelines, e.g. Twitter, Facebook, and Instagram"""

    async def run(self) -> None:
        # indicate we are not done
        self._done = False
        logger.debug(f"TimelineFeedBehavior.run")
        # check if we injected our setup code or not
        if not self._did_init:
            # did not so inject it
            await self.tab.evaluate_in_page(self._resource)
            self._did_init = True
        # get next timeline item
        done = await self.tab.evaluate_in_page("window.$WRIteratorHandler$()")
        logger.debug(f"TimelineFeedBehavior done ? {done}")
        # if we are done then tell the tab we are done
        if done.get("result").get("value"):
            self.tab.pause_behaviors()
            self._done = True
