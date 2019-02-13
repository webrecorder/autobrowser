import asyncio
import logging
from asyncio import AbstractEventLoop, Task
from typing import Awaitable, Any, Callable, Optional, Union

import attr
from simplechrome.frame_manager import Frame

from autobrowser.abcs import Behavior, Tab
from autobrowser.util import Helper

__all__ = ["WRBehaviorRunner"]

logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True)
class WRBehaviorRunner(Behavior):
    tab: Tab = attr.ib()
    behavior_js: str = attr.ib(repr=False)
    next_action_expression: str = attr.ib(
        default="window.$WRIteratorHandler$()", repr=False
    )
    collect_outlinks: bool = attr.ib(default=False)
    frame: Optional[Union[Frame, Callable[[], Frame]]] = attr.ib(default=None)
    _done: bool = attr.ib(default=False, init=False)
    _paused: bool = attr.ib(default=False, init=False)
    _did_init: bool = attr.ib(default=False, init=False)
    _running_task: Optional[Task] = attr.ib(default=None, init=False, repr=False)

    @property
    def done(self) -> bool:
        return self._done

    @property
    def paused(self) -> bool:
        return self._paused

    def reset(self) -> None:
        self._did_init = False
        self._done = False

    def end(self) -> None:
        self._done = True
        logger.info("WRBehaviorRunner[end]: ending unconditionally")

    async def init(self) -> None:
        if self._did_init:
            return
        logger.info("WRBehaviorRunner[init]: initializing the behavior")
        await self.pre_action_init()
        self._did_init = True
        await Helper.one_tick_sleep()

    async def pre_action_init(self) -> None:
        logger.info("WRBehaviorRunner[pre_action_init]: performing pre action init")
        # inject the behavior's javascript into the page
        try:
            await self.evaluate_in_page(self.behavior_js)
            await self.evaluate_in_page("window.$WBBehaviorPaused = false")
        except Exception as e:
            logger.exception(
                "WRBehaviorRunner[pre_action_init]: while initializing the behavior an exception was raised",
                exc_info=e,
            )
            raise
        logger.info("WRBehaviorRunner[pre_action_init]: performed pre action init")

    async def perform_action(self) -> None:
        logger.info("WRBehaviorRunner[perform_action]: performing the next action")
        next_state = await self.evaluate_in_page(self.next_action_expression)
        # if we are done then tell the tab we are done
        done = next_state.get("done")
        logger.info(
            f"WRBehaviorRunner[perform_action]: performed the next action, behavior state = {next_state}"
        )
        if not done and next_state.get("wait"):
            logger.info(
                "WRBehaviorRunner[perform_action]: waiting for network idle"
            )
            await self.tab.wait_for_net_idle(global_wait=30)
        elif done:
            self._finished()

    def evaluate_in_page(self, js_string: str) -> Awaitable[Any]:
        if self.frame is not None:
            logger.info("WRBehaviorRunner[evaluate_in_page]: using supplied frame")
            if callable(self.frame):
                frame = self.frame()
            else:
                frame = self.frame
            return frame.evaluate_expression(js_string, withCliAPI=True)
        logger.info("WRBehaviorRunner[evaluate_in_page]: using tab.evaluate_in_page")
        return self.tab.evaluate_in_page(js_string)

    async def run(self) -> None:
        logger.info("WRBehaviorRunner[run]: running behavior")
        await self.init()
        try:
            self.tab.set_running_behavior(self)
            self_perform_action = self.perform_action
            self_collect_outlinks = self.collect_outlinks
            self_tab_collect_outlinks = self.tab.collect_outlinks
            logger_info = logger.info
            helper_one_tick_sleep = Helper.one_tick_sleep
            while not self.done:
                logger_info("WRBehaviorRunner[run]: performing action")
                await self_perform_action()
                if self_collect_outlinks:
                    logger_info("WRBehaviorRunner[run]: collecting outlinks")
                    await self_tab_collect_outlinks()
                # we will wait 1 tick of the event loop before performing another action
                # in order to allow any other tasks to continue on
                if not self.done:
                    await helper_one_tick_sleep()
            logger.info("WRBehaviorRunner[run]: behavior done")
        except Exception as e:
            logger.exception(
                "WRBehaviorRunner[run]: while running an exception was raised",
                exc_info=e,
            )
            raise
        finally:
            self.tab.unset_running_behavior(self)

    def run_task(self, loop: Optional[AbstractEventLoop] = None) -> Task:
        if self._running_task is not None and not self._running_task.done():
            return self._running_task
        if loop is None:
            loop = asyncio.get_event_loop()
        self._running_task = loop.create_task(self.run())
        return self._running_task

    def _finished(self) -> None:
        self._done = True
        logger.info("WRBehaviorRunner[_finished]: ending")
