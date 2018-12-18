# -*- coding: utf-8 -*-
import asyncio
import logging
from abc import ABC, abstractmethod
from asyncio import Task, AbstractEventLoop
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, ClassVar, Union, TYPE_CHECKING

import aiofiles
import attr
from simplechrome.frame_manager import Frame

if TYPE_CHECKING:
    from ..tabs.basetab import Tab  # noqa: F401


__all__ = ["Behavior", "JSBasedBehavior"]

logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True)
class Behavior(ABC):
    """A behavior represents an action that is to be performed in the page (tab)
    or specific frame within the page.

    This class defines the expected interface for all behaviors.
    Each behavior has an associated tab and configuration. If a behaviors configuration is not supplied
    then it is an empty dictionary, allowing subclasses to fill in information as necessary.

    Behavior lifecycle:
     - run() -> init(), action loop
     - init() -> if (_has_resource): load_resources, if (pre_action_init) pre_action_init
     - action loop -> while(not done): perform_action
    """

    tab: "Tab" = attr.ib()
    conf: Dict = attr.ib(factory=dict)
    collect_outlinks: bool = attr.ib(default=False)
    frame: Optional[Union[Frame, Callable[[], Frame]]] = attr.ib(default=None)
    _has_resource: bool = attr.ib(default=False, init=False)
    _pre_init: bool = attr.ib(default=False, init=False)
    _done: bool = attr.ib(default=False, init=False)
    _paused: bool = attr.ib(default=False, init=False)
    _did_init: bool = attr.ib(default=False, init=False)
    _resource: str = attr.ib(default="", init=False, repr=False)
    _running_task: Optional[Task] = attr.ib(default=None, init=False, repr=False)
    _clz_name: str = attr.ib(init=False, default=None)

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

    @abstractmethod
    async def perform_action(self) -> None:
        """Perform the behaviors action in the page"""
        pass

    def reset(self) -> None:
        """Reset the behavior to its initial state"""
        self._did_init = False
        self._done = False

    def end(self) -> None:
        """Unconditionally set the behaviors running state to done"""
        self._done = True

    async def load_resources(self) -> Any:
        """Load the resources required by a behavior.

        Behaviors that require resources, typically JS, are expected to subclass JSBasedBehavior.
        """
        pass

    async def pre_action_init(self) -> None:
        """Perform all initialization required to run the behavior.

        Behaviors that require so setup before performing their actions
        should override this method in order to perform the required setup
        """
        pass

    async def init(self) -> None:
        """Initialize the behavior. If the behavior was previously initialized this is a no op.

        Loads the behaviors resources if _has_resource is true.
        Executes the behaviors pre-action init if _pre_init is true
        """
        if self._did_init:
            return
        logger.info(
            f"{self._clz_name}[init]: have resource = {self._has_resource}, pre init = {self._pre_init}"
        )
        if self._has_resource:
            await self.load_resources()
        if self._pre_init:
            await self.pre_action_init()
        self._did_init = True

    def run_task(self, loop: Optional[AbstractEventLoop] = None) -> Task:
        """Run the behavior as a task, if the behavior is already running as
        a task the running behavior run task is returned.

        :param loop: The event loop to task will be created using.
        Defaults to asyncio.get_event_loop()
        """
        if self._running_task is not None and not self._running_task.done():
            return self._running_task
        if loop is None:
            loop = asyncio.get_event_loop()
        self._running_task = loop.create_task(self.run())
        return self._running_task

    async def run(self) -> None:
        """Run the behaviors actions.

        Set the tabs running behavior at the start and
        once the behavior is finished (performed all actions)
        unsets the tabs running behavior.

        Behaviors lifecycle represented by invoking this method:
         - init
         - perform action while not done
         - call tab.collect_outlinks if collection outlinks
         after an action was performed
        """
        await self.init()
        logger.info(f"{self._clz_name}[run]: running behavior")
        self.tab.set_running_behavior(self)
        while not self.done:
            await self.perform_action()
            if self.collect_outlinks:
                await self.tab.collect_outlinks()
        logger.info(f"{self._clz_name}[run]: behavior done")
        self.tab.unset_running_behavior(self)

    def evaluate_in_page(self, js_string: str) -> Awaitable[Any]:
        """Evaluate a string of JavaScript inside the page or frame.

        :param js_string: The string of JavaScript to be evaluated
        """
        if self.frame is not None:
            if callable(self.frame):
                frame = self.frame()
            else:
                frame = self.frame
            return frame.evaluate_expression(js_string, withCliAPI=True)
        return self.tab.evaluate_in_page(js_string)

    def _finished(self) -> None:
        """Sets the state of the behavior to done"""
        self._done = True

    def __attrs_post_init__(self) -> None:
        self._pre_init = self.conf.get("pre_init", self._pre_init)
        self._clz_name = self.__class__.__name__

    def __await__(self) -> Any:
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

    async def pre_action_init(self) -> None:
        logger.info(f"{self._clz_name}[pre_action_init]: performing pre action init")
        # check if we injected our setup code or not
        # did not so inject it
        await self.evaluate_in_page(self._resource)

    async def load_resources(self) -> None:
        resource = self.conf.get("resource")
        is_pkg = self.conf.get("pkg_resource", True)
        logger.info(
            f"{self._clz_name}[load_resources]: loading {'pgk' if is_pkg else 'external'} resource"
        )
        if is_pkg:
            resource = str(Path(__file__).parent / "behaviorjs" / resource)
        async with aiofiles.open(resource, "r") as iin:
            self._resource = await iin.read()
        logger.info(f"{self._clz_name}[load_resources]: resources loaded")
