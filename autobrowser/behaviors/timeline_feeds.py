# -*- coding: utf-8 -*-
import logging
from typing import Dict

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
            await self.tab.evaluate_in_page(self._resource, contextId=self.contextId)
            self._did_init = True
        # get next timeline item
        done = await self.tab.evaluate_in_page(
            self._wr_action_iter_next, contextId=self.contextId
        )
        logger.debug(f"TimelineFeedBehavior done ? {done}")
        # if we are done then tell the tab we are done
        if done.get("result").get("value"):
            self.tab.pause_behaviors()
            self._done = True


class TimelineFeedNetIdle(JSBasedBehavior):
    """Behavior for iterating over timelines or feeds where every action may require use to wait for
    network idle to happen before initiating another
    """

    async def run(self) -> None:
        # indicate we are not done
        self._done = False
        logger.debug(f"TimelineFeedBehavior.run")
        # check if we injected our setup code or not
        if not self._did_init:
            # did not so inject it
            await self.tab.evaluate_in_page(self._resource, contextId=self.contextId)
            self._did_init = True
        # get next timeline item
        next_state = await self.tab.evaluate_in_page(
            self._wr_action_iter_next, contextId=self.contextId
        )
        logger.debug(f"TimelineFeedBehavior done ? {next_state}")
        # if we are done then tell the tab we are done
        result = next_state.get("result", {}).get("value")
        done = result.get("done")
        if not done and result.get("wait"):
            await self.tab.net_idle(global_wait=10)
        elif done:
            self.tab.pause_behaviors()
            self._done = True
