import logging
from typing import Any

from autobrowser.util.helper import Helper
from .basetab import BaseTab

__all__ = ["BehaviorTab"]

logger = logging.getLogger("autobrowser")


class BehaviorTab(BaseTab):
    @classmethod
    def create(cls, *args, **kwargs) -> "BehaviorTab":
        return cls(*args, **kwargs)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._page_url_expression: str = "window.location.href"
        self._pflag_exists_expression: str = (
            "typeof window.$WBBehaviorPaused !== 'undefined'"
        )

    async def resume_behaviors(self) -> None:
        await super().resume_behaviors()
        url = await self.evaluate_in_page(self._page_url_expression)
        behavior_paused_flag = await self.evaluate_in_page(
            self._pflag_exists_expression
        )
        behavior_not_running = (
            self._running_behavior is None or self._running_behavior.done
        )
        logger.debug(
            f"BehaviorTab[resume_behaviors]: page url = {url}, paused flag exists = {behavior_paused_flag}, "
            f"and behavior not running {behavior_not_running}"
        )
        url_change = url != self._curr_behavior_url and not behavior_paused_flag
        # if no behavior running, restart behavior for current page
        if behavior_not_running or url_change:
            await self._ensure_behavior_run_task_end()
            self._curr_behavior_url = url
            logger.debug(f"BehaviorTab[resume_behaviors]: Restarting behavior")
            await self._run_behavior_for_current_url()
        logger.debug(f"BehaviorTab[resume_behaviors]: Behavior resumed")

    async def init(self) -> None:
        if self._running:
            return
        await super().init()
        self._curr_behavior_url = self.tab_data.get("url")
        await Helper.one_tick_sleep()

    async def close(self) -> None:
        logger.info(f"BehaviorTab[close]: closing")
        await self._ensure_behavior_run_task_end()
        await super().close()

    async def _ensure_behavior_run_task_end(self) -> None:
        if self._behavior_run_task is not None and not self._behavior_run_task.done():
            logger.debug(
                f"BehaviorTab[_ensure_behavior_run_task_end]: we have an existing behavior stopping it"
            )
            try:
                await Helper.timed_future_completion(
                    self._behavior_run_task, cancel=True, loop=self.loop
                )
            except Exception as e:
                logger.exception(
                    "BehaviorTab[_ensure_behavior_run_task_end]: the current behavior_run_task "
                    "threw an unexpected exception while waiting for it to end",
                    exc_info=e,
                )
            self._behavior_run_task = None

    async def _run_behavior_for_current_url(self) -> None:
        behavior = await self.behavior_manager.behavior_for_url(
            self._curr_behavior_url, self
        )
        logger.debug(
            f"BehaviorTab[_run_behavior_for_current_url]: starting behavior {behavior} for {self._curr_behavior_url}"
        )
        self._behavior_run_task = self.loop.create_task(behavior.run())
