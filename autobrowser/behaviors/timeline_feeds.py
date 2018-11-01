# -*- coding: utf-8 -*-
import logging
from typing import Dict

from .basebehavior import JSBasedBehavior

__all__ = ["TimelineFeedBehavior"]

logger = logging.getLogger("autobrowser")


class TimelineFeedBehavior(JSBasedBehavior):
    """Behavior for iterating over timelines, e.g. Twitter, Facebook, and Instagram"""

    async def perform_action(self) -> None:
        logger.debug(f"TimelineFeedBehavior.perform_action")
        # get next timeline item
        done = await self.tab.evaluate_in_page(
            self._wr_action_iter_next, contextId=self.contextId
        )
        logger.debug(f"TimelineFeedBehavior done ? {done}")
        # if we are done then tell the tab we are done
        if done.get("result").get("value"):
            self._finished()


class TimelineFeedNetIdle(JSBasedBehavior):
    """Behavior for iterating over timelines or feeds where every action may require use to wait for
    network idle to happen before initiating another
    """

    async def perform_action(self) -> None:
        # indicate we are not done
        logger.debug(f"TimelineFeedBehavior.perform_action")
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
            self._finished()

