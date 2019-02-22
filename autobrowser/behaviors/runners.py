from asyncio import (
    AbstractEventLoop,
    CancelledError as AIOCancelledError,
    Task,
    TimeoutError as AIOTimeoutError,
)
from typing import Any, Awaitable, Callable, Optional, Union

from async_timeout import timeout as aio_timeout
from attr import dataclass as attr_dataclass, ib as attr_ib
from simplechrome.frame_manager import Frame

from autobrowser.abcs import Behavior, Tab
from autobrowser.util import AutoLogger, Helper, create_autologger

__all__ = ["WRBehaviorRunner"]


@attr_dataclass(slots=True)
class WRBehaviorRunner(Behavior):
    tab: Tab = attr_ib()
    behavior_js: str = attr_ib(repr=False)
    next_action_expression: str = attr_ib(
        default="window.$WRIteratorHandler$()", repr=False
    )
    collect_outlinks: bool = attr_ib(default=False)
    frame: Optional[Union[Frame, Callable[[], Frame]]] = attr_ib(default=None)
    loop: AbstractEventLoop = attr_ib(default=None, repr=False)
    logger: AutoLogger = attr_ib(init=False, default=None, repr=False)
    _done: bool = attr_ib(default=False, init=False)
    _paused: bool = attr_ib(default=False, init=False)
    _did_init: bool = attr_ib(default=False, init=False)
    _running_task: Optional[Task] = attr_ib(default=None, init=False, repr=False)

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
        self.logger.info("end", "ending unconditionally")

    async def init(self) -> None:
        if self._did_init:
            return
        self.logger.info("init", "initializing the behavior")
        await self.pre_action_init()
        self._did_init = True
        await Helper.one_tick_sleep()

    async def pre_action_init(self) -> None:
        self.logger.info("pre_action_init", "performing pre action init")
        # inject the behavior's javascript into the page
        try:
            await self.evaluate_in_page(self.behavior_js)
            await self.evaluate_in_page("window.$WBBehaviorPaused = false")
        except Exception as e:
            self.logger.exception(
                "pre_action_init",
                "while initializing the behavior an exception was raised",
                exc_info=e,
            )
            raise
        self.logger.info("pre_action_init", "performed pre action init")

    async def perform_action(self) -> None:
        self.logger.info("perform_action", "performing the next action")
        next_state = await self.evaluate_in_page(self.next_action_expression)
        # if we are done then tell the tab we are done
        done = next_state.get("done")
        self.logger.info(
            "perform_action",
            f"performed the next action, behavior state = {next_state}",
        )
        if not done and next_state.get("wait"):
            self.logger.info("perform_action", "waiting for network idle")
            await self.tab.wait_for_net_idle(global_wait=30)
        elif done:
            self._finished()

    def evaluate_in_page(self, js_string: str) -> Awaitable[Any]:
        if self.frame is not None:
            self.logger.info("evaluate_in_page", "using supplied frame")
            return self.__get_frame().evaluate_expression(js_string, withCliAPI=True)
        self.logger.info("evaluate_in_page", "using tab.evaluate_in_page")
        return self.tab.evaluate_in_page(js_string)

    async def run(self) -> None:
        logged_method = "run"
        performing_action_msg = "performing action"
        collecting_outlinks_msg = "collecting outlinks"

        self.logger.info(logged_method, "running behavior")
        try:
            await self.init()
        except Exception as e:
            self.logger.exception(
                logged_method,
                "while attempting to initialize the behavior an exception was raised",
                exc_info=e,
            )
            raise

        self.tab.set_running_behavior(self)

        self_logger_info = self.logger.info
        self_perform_action = self.perform_action
        self_collect_outlinks = self.collect_outlinks
        self_tab_collect_outlinks = self.tab.collect_outlinks
        self__done = self.__done
        helper_one_tick_sleep = Helper.one_tick_sleep

        try:
            while 1:
                self_logger_info(logged_method, performing_action_msg)
                await self_perform_action()
                if self_collect_outlinks:
                    self_logger_info(logged_method, collecting_outlinks_msg)
                    await self_tab_collect_outlinks()
                # we will wait 1 tick of the event loop before performing another action
                # in order to allow any other tasks to continue on
                if not self__done():
                    await helper_one_tick_sleep()
                else:
                    break
            self_logger_info(logged_method, "behavior done")
        except AIOCancelledError:
            pass
        except Exception as e:
            self.logger.exception(
                logged_method, "while running an exception was raised", exc_info=e
            )
            raise
        finally:
            self.tab.unset_running_behavior(self)

    async def timed_run(self, max_run_time: Union[int, float]) -> None:
        try:
            async with aio_timeout(max_run_time, loop=self.loop):
                await self.run()
        except AIOTimeoutError:
            self.logger.info("timed_run", f"the maximum run time was exceeded <max_run_time={max_run_time}>")
        except AIOCancelledError:
            pass
        except Exception:
            raise

    def run_task(self) -> Task:
        if self._running_task is not None and not self._running_task.done():
            return self._running_task
        self._running_task = self.loop.create_task(self.run())
        return self._running_task

    def timed_run_task(self, max_run_time: Union[int, float]) -> Task:
        if self._running_task is not None and not self._running_task.done():
            return self._running_task
        self._running_task = self.loop.create_task(self.timed_run(max_run_time))
        return self._running_task

    def _finished(self) -> None:
        self._done = True
        self.logger.info("_finished", "ending")

    def __done(self) -> bool:
        return self._done

    def __get_frame(self) -> Frame:
        if callable(self.frame):
            return self.frame()
        return self.frame

    def __attrs_post_init__(self) -> None:
        if self.loop is None:
            self.loop = Helper.event_loop()
        self.logger = create_autologger("behaviorRunner", "WRBehaviorRunner")
