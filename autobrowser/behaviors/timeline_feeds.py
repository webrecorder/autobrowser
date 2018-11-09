# -*- coding: utf-8 -*-
import logging

from .basebehavior import JSBasedBehavior

__all__ = ["TimelineFeedBehavior"]

logger = logging.getLogger("autobrowser")


class TimelineFeedBehavior(JSBasedBehavior):
    """Behavior for iterating over timelines, e.g. Twitter, Facebook, and Instagram"""

    async def perform_action(self) -> None:
        # get next timeline item
        done = await self.evaluate_in_page(self._wr_action_iter_next)
        # if we are done then tell the tab we are done
        if done:
            self._finished()


class TimelineFeedNetIdle(JSBasedBehavior):
    """Behavior for iterating over timelines or feeds where every action may require use to wait for
    network idle to happen before initiating another
    """

    async def perform_action(self) -> None:
        # indicate we are not done
        # get next timeline item
        next_state = await self.evaluate_in_page(self._wr_action_iter_next)

        # if we are done then tell the tab we are done
        done = next_state.get("done")
        if not done and next_state.get("wait"):
            logger.info(f"TimelineFeedBehavior[perform_action]: waiting for network idle")
            await self.tab.net_idle(global_wait=10)
        elif done:
            self._finished()
