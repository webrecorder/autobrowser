from asyncio import AbstractEventLoop, CancelledError, Task, TimeoutError
from typing import Any, Awaitable, Callable, Optional, Union

from async_timeout import timeout
from simplechrome.frame_manager import Frame

from autobrowser.abcs import Behavior, Tab
from autobrowser.util import AutoLogger, Helper, create_autologger

__all__ = ["WRBehaviorRunner"]


class WRBehaviorRunner(Behavior):
    __slots__ = [
        "__weakref__",
        "_did_init",
        "_done",
        "_num_actions_performed",
        "_paused",
        "_running_task",
        "behavior_js",
        "collect_outlinks",
        "frame",
        "logger",
        "loop",
        "next_action_expression",
        "tab",
        "take_screen_shot",
    ]

    def __init__(
        self,
        behavior_js: str,
        tab: Tab,
        next_action_expression: str,
        loop: Optional[AbstractEventLoop] = None,
        collect_outlinks: bool = False,
        take_screen_shot: bool = False,
        frame: Optional[Union[Frame, Callable[[], Frame]]] = None,
    ) -> None:
        """Initialize the new WRBehaviorRunner instance

        :param behavior_js: The behavior's JS
        :param tab: The tab the behavior's JS will be run in
        :param next_action_expression: The JS expression used to initiate a behavior's action
        :param loop: The event loop used by the automation
        :param collect_outlinks: Should outlinks be collected after each action
        :param take_screen_shot: Should a screenshot be taken once the behavior is done
        :param frame: Optional reference to or callable returning a simplechrome.FrameManager.Frame
        that the behavior is to be run in
        """
        self.behavior_js: str = behavior_js
        self.tab: Tab = tab
        self.next_action_expression: str = next_action_expression
        self.collect_outlinks: bool = collect_outlinks
        self.take_screen_shot: bool = take_screen_shot
        self.frame: Optional[Union[Frame, Callable[[], Frame]]] = frame
        self.loop: AbstractEventLoop = Helper.ensure_loop(loop)
        self.logger: AutoLogger = create_autologger(
            "behaviorRunner", "WRBehaviorRunner"
        )
        self._done: bool = False
        self._paused: bool = False
        self._did_init: bool = False
        self._running_task: Optional[Task] = None
        self._num_actions_performed: int = 0

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
        self.logger.debug("end", "ending unconditionally")

    async def init(self) -> None:
        if self._did_init:
            return
        self.logger.debug("init", "initializing the behavior")
        await self.pre_action_init()
        self._did_init = True
        await Helper.one_tick_sleep()

    def evaluate_in_page(self, js_string: str) -> Awaitable[Any]:
        if self.frame is not None:
            self.logger.debug("evaluate_in_page", "using supplied frame")
            return self.__get_frame().evaluate_expression(js_string, withCliAPI=True)
        self.logger.debug("evaluate_in_page", "using tab.evaluate_in_page")
        return self.tab.evaluate_in_page(js_string)

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

    async def pre_action_init(self) -> None:
        self.logger.debug("pre_action_init", "performing pre action init")
        # inject the behavior's javascript into the page
        try:
            await self.evaluate_in_page(self.behavior_js)
            await self.evaluate_in_page(self.tab.config.unpause_behavior_expression)
        except Exception as e:
            self.logger.exception(
                "pre_action_init",
                "while initializing the behavior an exception was raised",
                exc_info=e,
            )
            raise
        self.logger.debug("pre_action_init", "performed pre action init")

    async def perform_action(self) -> None:
        self.logger.debug("perform_action", "performing the next action")
        next_state = await self.evaluate_in_page(self.next_action_expression)
        # if we are done then tell the tab we are done
        done = next_state.get("done")
        self.logger.debug(
            "perform_action",
            f"performed the next action, behavior state = {next_state}",
        )
        if done or self._done:
            return self._finished()
        if next_state.get("wait"):
            self.logger.debug("perform_action", "waiting for network idle")
            await self.tab.wait_for_net_idle(global_wait=30)

    async def run(self) -> None:
        logged_method = "run"
        self.logger.debug(logged_method, "running behavior")

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

        try:
            await self._action_loop()
            self.logger.debug(logged_method, "behavior done")
        except CancelledError:
            pass
        except Exception as e:
            self.logger.exception(
                logged_method, "while running an exception was raised", exc_info=e
            )
            raise
        finally:
            await self._post_run()

    async def timed_run(self, max_run_time: Union[int, float]) -> None:
        """Runs the behavior until the maximum run time has been reached

        :param max_run_time: The maximum amount of time the behavior is allowed to run
        """
        try:
            async with timeout(max_run_time, loop=self.loop):
                await self.run()
        except TimeoutError:
            self.logger.debug(
                "timed_run",
                f"the maximum run time was exceeded <max_run_time={max_run_time}>",
            )
        except CancelledError:
            pass
        except Exception:
            raise

    async def _action_loop(self) -> None:
        """The main behavior action loop.

        Steps:
          - perform behavior action
          - if not done perform the configured post behavior action action's
          - if done exit loop
          - sleep for one tick
        """
        perform_action = self.perform_action
        post_action = self._post_action
        behavior_done = self.__done
        helper_one_tick_sleep = Helper.one_tick_sleep

        while 1:
            await perform_action()
            if not behavior_done():
                await post_action()
            else:
                break
            # we will wait 1 tick of the event loop before performing another action
            # in order to allow any other tasks to continue on
            await helper_one_tick_sleep()

    async def _post_action(self) -> None:
        """Executes the actions we are configured to do after an behavior's action.

        Available post run actions:
         - Out link collection
        """
        logged_method = "post action"
        self.logger.debug(
            logged_method, Helper.json_string(action_count=self._num_actions_performed)
        )
        self._num_actions_performed += 1
        # If the behavior runner is configured to collect out links, the collection occurs after every 10
        # actions initiated. This is done in order to ensure that the performance of running an behavior does
        # not degrade due to a page having lots of out links (10k+).
        # Note: the previous handling of out links was to collect them after every action
        if self.collect_outlinks and self._num_actions_performed % 10 == 0:
            self.logger.debug(logged_method, f"collecting outlinks")
            await self.tab.collect_outlinks()

    async def _post_run(self) -> None:
        """Executes the actions we are configured to do after the behavior has run.

        Available post run actions:
          - Take and upload a screen shot
          - Out link collection
        """
        if self.take_screen_shot:
            await Helper.no_raise_await(self.tab.capture_and_upload_screenshot())
        # collect any remaining out links collected by the behavior
        # done in _post_run due to new handling of out link collection
        if self.collect_outlinks:
            await Helper.no_raise_await(self.tab.collect_outlinks(True))
        self.tab.unset_running_behavior(self)

    def _finished(self) -> None:
        self._done = True
        self.logger.info("_finished", "ending")

    def __done(self) -> bool:
        """Utility method for the action loop in run
        that returns T/F indicating if the behavior is done

        :return: T/F indicating if the behavior is done
        """
        return self._done

    def __get_frame(self) -> Frame:
        """Utility method for evaluate_in_page that returns the
        simplechrome.FrameManager.Frame to be used

        :return: the simplechrome.FrameManager.Frame to be used
        """
        if callable(self.frame):
            return self.frame()
        return self.frame

    def __str__(self) -> str:
        info = f"done={self._done}, paused={self._paused}, init={self._did_init}"
        return f"WRBehaviorRunner({info}, outlinks={self.collect_outlinks}, screenshot={self.take_screen_shot})"

    def __repr__(self) -> str:
        return self.__str__()
