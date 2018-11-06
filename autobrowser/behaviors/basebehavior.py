# -*- coding: utf-8 -*-
import asyncio
from abc import ABC, abstractmethod
from asyncio import Task, AbstractEventLoop
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, ClassVar, Awaitable, Any
from simplechrome.frame_manager import Frame

import aiofiles
import attr

if TYPE_CHECKING:
    from ..tabs.basetab import BaseAutoTab  # noqa: F401


__all__ = ["Behavior", "JSBasedBehavior"]


@attr.dataclass(slots=True)
class Behavior(ABC):
    """A behavior represents an action that is to be performed in the page (tab).

    This class defines the expected interface for all behaviors.
    Each behavior has an associated tab and configuration. If a behaviors configuration is not supplied
    then it is an empty dictionary, allowing subclasses to fill in information as necessary.

    Behavior lifecycle:
      - init():
        called
    - run() -> done

    """

    tab: "BaseAutoTab" = attr.ib()
    conf: Dict = attr.ib(factory=dict)
    frame: Optional[Frame] = attr.ib(default=None)
    _has_resource: bool = attr.ib(default=False, init=False)
    _pre_init: bool = attr.ib(default=False, init=False)
    _done: bool = attr.ib(default=False, init=False)
    _paused: bool = attr.ib(default=False, init=False)
    _did_init: bool = attr.ib(default=False, init=False)
    _resource: str = attr.ib(default="", init=False)
    _running_task: Optional[Task] = attr.ib(default=None, init=False)

    def __attrs_post_init__(self):
        self._pre_init = self.conf.get("pre_init", self._pre_init)

    @property
    def done(self) -> bool:
        """Is the behavior done"""
        return self._done

    @property
    def paused(self) -> bool:
        """Is the behavior paused.

        A behavior in the paused state indicates that it has yet to reach its know completion point,
        but is waiting for some condition to occur before resuming.
        """
        return self._paused

    @property
    def has_resources(self) -> bool:
        """Does the behavior require resources to be loaded"""
        return self._has_resource

    def reset(self):
        self._did_init = False
        self._done = False

    def _finished(self):
        self.tab.pause_behaviors()
        self._done = True

    @abstractmethod
    async def perform_action(self) -> None:
        pass

    async def load_resources(self):
        """Load the resources required by a behavior.

        Behaviors that require resources, typically JS, are expected to subclass JSBasedBehavior.
        """
        pass

    async def pre_action_init(self) -> None:
        """Perform all initialization required to run the behavior.

        Behaviors that require
        """
        pass

    async def init(self) -> None:
        if self._did_init:
            return
        if self._has_resource:
            await self.load_resources()
        if self._pre_init:
            await self.pre_action_init()
        self._did_init = True

    def run_task(
        self, loop: Optional[AbstractEventLoop] = None
    ) -> Task:
        if self._running_task is not None and not self._running_task.done():
            return self._running_task
        if loop is None:
            loop = asyncio.get_event_loop()
        self._running_task = loop.create_task(self.run())
        return self._running_task

    async def run(self) -> None:
        await self.init()
        while not self.done:
            await self.perform_action()

    async def evaluate_in_page(self, js_string: str) -> Any:
        if self.frame is not None:
            return await self.frame.evaluate_expression(js_string, withCliAPI=True)
        result = await self.tab.evaluate_in_page(js_string)
        return result.get("result", {}).get("value")

    def __await__(self):
        return self.run().__await__()


@attr.dataclass(slots=True)
class JSBasedBehavior(Behavior, ABC):
    """Specialized subclass of Behavior that require JavaScript to operate.

    The name of the JavaScript file a subclassing behavior requires is expected to
    be contained in the conf property under the 'resource' key. If the key 'pkg_resource'
    is false then the value of the 'resource' key is expected to be a full path to the file.
    """

    _has_resource: bool = attr.ib(default=True, init=False)
    _pre_init: bool = attr.ib(default=True, init=False)
    _wr_action_iter_next: ClassVar[str] = "window.$WRIteratorHandler$()"

    async def pre_action_init(self):
        # check if we injected our setup code or not
        # did not so inject it
        await self.evaluate_in_page(self._resource)

    async def load_resources(self) -> None:
        resource = self.conf.get("resource")
        if self.conf.get("pkg_resource", True):
            resource = str(Path(__file__).parent / "behaviorjs" / resource)
        async with aiofiles.open(resource, "r") as iin:
            self._resource = await iin.read()
