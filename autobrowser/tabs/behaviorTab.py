# -*- coding: utf-8 -*-
import asyncio
import logging

from autobrowser.behaviors.behavior_manager import BehaviorManager
from autobrowser.behaviors.basebehavior import Behavior
from .basetab import Tab

__all__ = ["BehaviorTab"]

logger = logging.getLogger("autobrowser")


class BehaviorTab(Tab):
    def unset_running_behavior(self, behavior: Behavior) -> None:
        if self._running_behavior and behavior is self._running_behavior:
            self._running_behavior = None
            if self._behavior_run_task and not self._behavior_run_task.done():
                self._behavior_run_task.cancel()
            self._behavior_run_task = None

    async def resume_behaviors(self) -> None:
        await super().resume_behaviors()
        # if no behavior running, restart behavior for current page
        if not self._running_behavior or self._running_behavior.done:
            logger.debug(f"BehaviorTab: Restarting behavior")
            url = await self.evaluate_in_page("window.location.href")
            logger.debug(f"BehaviorTab: behavior url = {url}")
            await self._ensure_behavior_run_task_end()
            behavior = BehaviorManager.behavior_for_url(url, self)
            self.set_running_behavior(behavior)
            self._behavior_run_task = self.loop.create_task(behavior.run())

    async def init(self) -> None:
        if self._running:
            return
        await super().init()
        behavior = BehaviorManager.behavior_for_url(self.tab_data.get("url"), self)
        self._behavior_run_task = self.loop.create_task(behavior.run())

    async def close(self) -> None:
        logger.info(f"BehaviorTab[close]: closing")
        await self._ensure_behavior_run_task_end()
        await super().close()

    @classmethod
    def create(cls, *args, **kwargs) -> "BehaviorTab":
        return cls(*args, **kwargs)

    async def _ensure_behavior_run_task_end(self) -> None:
        if self._behavior_run_task and not self._behavior_run_task.done():
            self._behavior_run_task.cancel()
            try:
                await self._behavior_run_task
            except asyncio.CancelledError:
                pass
            self._behavior_run_task = None
