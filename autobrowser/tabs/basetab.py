# -*- coding: utf-8 -*-
"""Abstract Base Classes That Defines An Interface For Remote Browser Tabs"""
import asyncio
import logging
from abc import ABCMeta, abstractmethod
from asyncio import Task, AbstractEventLoop
from typing import List, Optional, Dict, Any, TYPE_CHECKING, ClassVar

import attr
from aioredis import Redis
from cripy import Client, connect
from pyee import EventEmitter

from autobrowser.automation import ShutdownCondition
from autobrowser.behaviors import BehaviorManager
from autobrowser.behaviors.basebehavior import Behavior
from autobrowser.util.netidle import monitor

if TYPE_CHECKING:
    from autobrowser.browser import Browser  # noqa: F401

__all__ = ["Tab"]

logger = logging.getLogger("autobrowser")


@attr.dataclass(frozen=True)
class TabEvents(object):
    Crashed: str = attr.ib(default='Tab:Crashed')
    ConnectionClosed: str = attr.ib(default='Tab:ConnectionClosed')


class Tab(EventEmitter, metaclass=ABCMeta):
    """Base Automation Tab Class that represents a browser tab in a running browser"""

    Events: ClassVar[TabEvents] = TabEvents()

    def __init__(
        self,
        browser: "Browser",
        tab_data: Dict[str, str],
        redis: Optional[Redis] = None,
        sd_condition: Optional[ShutdownCondition] = None,
        **kwargs,
    ) -> None:
        if browser is not None:
            loop: AbstractEventLoop = browser.loop
        else:
            loop: AbstractEventLoop = asyncio.get_event_loop()
        super().__init__(loop=loop)
        self.browser: "Browser" = browser
        self.redis = redis
        self.tab_data: Dict[str, str] = tab_data
        self.client: Client = None
        self.behaviors: List[Behavior] = []
        self.all_behaviors: Optional[Task] = None
        self.target_info: Optional[Dict] = None
        self.sd_condition = sd_condition
        self._url: str = self.tab_data["url"]
        self._id: str = self.tab_data["id"]
        self._behaviors_paused: bool = False
        self._running: bool = False
        self._reconnecting: bool = False
        self._reconnect_promise: Optional[Task] = None
        self._behavior: Optional[Behavior] = None
        self._graceful_shutdown: bool = False
        self._running_behavior: Optional[Behavior] = None
        self._clz_name = self.__class__.__name__

    @property
    def loop(self) -> AbstractEventLoop:
        return self._loop

    @property
    def behaviors_paused(self) -> bool:
        """Are the behaviors paused"""
        return self._behaviors_paused

    @property
    def tab_id(self) -> str:
        """Returns the id of the tab this class is controlling"""
        return self._id

    @property
    def tab_url(self) -> str:
        """Returns the URL of the tab this class is controlling"""
        return self._url

    @property
    def running(self) -> bool:
        """Is this tab running (active client connection)"""
        return self._running

    @property
    def reconnecting(self) -> bool:
        """Is this tab attempting to reconnect to the tab"""
        return self._running and self._reconnecting

    def add_behavior(self, behavior: Behavior) -> None:
        """A Page behavior to the list of behaviors to be run per page

        :param behavior: The behavior to be added
        """
        self.behaviors.append(behavior)

    def set_running_behavior(self, behavior: Behavior) -> None:
        self._running_behavior = behavior

    def unset_running_behavior(self, behavior: Behavior) -> None:
        if self._running_behavior and behavior is self._running_behavior:
            self._running_behavior = None

    async def pause_behaviors(self) -> None:
        """Sets the behaviors paused flag to true"""
        await self.evaluate_in_page("window.$WBBehaviorPaused = true;")
        self._behaviors_paused = True

    async def resume_behaviors(self) -> None:
        """Sets the behaviors paused flag to false"""
        await self.evaluate_in_page("window.$WBBehaviorPaused = false;")

        # if no behavior running, restart behavior for current page
        if not self._running_behavior or self._running_behavior.done:
            logger.debug(f'Restarting behavior')
            url = await self.evaluate_in_page("window.location.href")
            logger.debug(f'Behavior url: {url}')
            behavior = BehaviorManager.behavior_for_url(url, self)
            self.behaviors = [behavior]
            self.all_behaviors = self._loop.create_task(self._behavior_loop())

        self._behaviors_paused = False

    def stop_reconnecting(self) -> None:
        """Stops the reconnection process if it is under way"""
        if not self.reconnecting or self._reconnect_promise is None:
            return
        if self._reconnect_promise.done():
            return
        try:
            self._reconnect_promise.cancel()
        except Exception:
            pass
        self._reconnecting = False

    def devtools_reconnect(self, result: Dict[str, str]) -> None:
        """Callback used to reconnect to the browser tab when the client connection was
        replaced with the devtools."""
        if result["reason"] == "replaced_with_devtools":
            self._reconnecting = True
            self._running = False
            self._reconnect_promise = self._loop.create_task(self._wait_for_reconnect())

    async def wait_for_reconnect(self) -> None:
        """If the client connection has been disconnected and we are
        reconnecting, waits for reconnection to happen"""
        if not self.reconnecting or self._reconnect_promise is None:
            return
        if self._reconnect_promise.done():
            return
        await self._reconnect_promise

    def net_idle(self, *args: Any, **kwargs: Any) -> Task:
        """Returns a future that  resolves once network idle occurs.

        See the options of autobrowser.util.netidle.monitor for a complete
        description of the available arguments
        """
        return monitor(self.client, *args, **kwargs)

    async def _wait_for_reconnect(self) -> None:
        """Attempt to reconnect to browser tab after client connection was replayed with
        the devtools"""
        while True:
            try:
                await self.init()
                break
            except Exception as e:
                print(e)

            await asyncio.sleep(3.0)
        self._reconnecting = False
        if self._reconnect_promise and not self._reconnect_promise.done():
            self._reconnect_promise.cancel()

    async def evaluate_in_page(
        self, js_string: str, contextId: Optional[Any] = None
    ) -> Any:
        """Evaluates the supplied string of JavaScript in the tab

        :param js_string: The string of JavaScript to be evaluated
        :return: The results of the evaluation if any
        """
        logger.info(f"{self._clz_name}[evaluate_in_page]: evaluating js in page")
        results = await self.client.Runtime.evaluate(
            js_string,
            contextId=contextId,
            userGesture=True,
            awaitPromise=True,
            includeCommandLineAPI=True,
            returnByValue=True,
        )
        return results.get("result", {}).get("value")

    async def goto(self, url: str, **kwargs: Any) -> Dict:
        """Initiates browser navigation to the supplied url.

        See cripy.protocol.Page for more information about additional
        arguments or https://chromedevtools.github.io/devtools-protocol/tot/Page#method-navigate

        :param url: The URL to be navigated to
        :param kwargs: Additional arguments to Page.navigate
        :return: The information returned by Page.navigate
        """
        logger.info(f"{self._clz_name}[goto]: navigating to {url}")
        return await self.client.Page.navigate(url, **kwargs)

    @classmethod
    @abstractmethod
    def create(cls, *args: Any, **kwargs: Any) -> "Tab":
        """Abstract method for creating new instances of a tab.

        Subclasses are expected to supply the means for creating
        themselves their implementation
        """
        pass

    async def connect_to_tab(self) -> None:
        if self._running:
            return
        logger.info(
            f"{self._clz_name}[connect_to_tab]: connecting to the browser {self.tab_data}"
        )
        self.client = await connect(self.tab_data["webSocketDebuggerUrl"], remote=True)

        logger.info(f"{self._clz_name}[connect_to_tab]: connected to browser")

        self.client.set_close_callback(self._on_connection_closed)

        self.client.Inspector.detached(self.devtools_reconnect)
        self.client.Inspector.targetCrashed(self._on_inspector_crashed)

        await asyncio.gather(
            self.client.Page.enable(),
            self.client.Network.enable(),
            self.client.Runtime.enable(),
            loop=self.loop
        )

        logger.info(f"{self._clz_name}[init]: enabled domains")

    @abstractmethod
    async def init(self) -> None:
        """Initialize the client connection to the tab.

        Subclasses are expected to call this method from their
        implementation. This can be the only call in their
        implementation.
        """
        logger.info(f"{self._clz_name}[init]: running = {self.running}")
        if self._running:
            return
        await self.connect_to_tab()
        self._running = True

    @abstractmethod
    async def close(self) -> None:
        """Close the client connection to the tab.

        Subclasses are expected to call this method from their
        implementation. This can be the only call in their
        implementation.
        """
        self._running = False
        logger.info(f"{self._clz_name}[close]: closing client")
        if self.reconnecting:
            self.stop_reconnecting()
        if self.client:
            await self.client.dispose()
            self.client = None

    async def shutdown_gracefully(self) -> None:
        logger.info(f"{self._clz_name}[shutdown_gracefully]: shutting down")
        self._graceful_shutdown = True
        await self.close()

    async def collect_outlinks(self) -> None:
        pass

    def _on_inspector_crashed(self, *args: Any, **kwargs: Any) -> None:
        self.emit(self.Events.Crashed, self.tab_id)
        logger.critical(f"{self._clz_name}[_on_inspector_crashed]: target Crashed {args[0]}")

    def _on_connection_closed(self) -> None:
        if self._running:
            logger.critical(f"{self._clz_name}<url={self._url}>[_on_connection_closed]: connection closed while running")
            self.emit(self.Events.ConnectionClosed, self.tab_id)

    def __str__(self) -> str:
        return f"{self._clz_name}(tab_id={self.tab_id}, url={self._url})"

    def __repr__(self) -> str:
        return self.__str__()
