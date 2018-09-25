# -*- coding: utf-8 -*-
"""Abstract Base Classes That Defines An Interface For Remote Browser Tabs"""
import asyncio
import logging
from abc import ABCMeta, abstractmethod
from asyncio import Future
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from cripy import Client, connect
from pyee import EventEmitter

from autobrowser.behaviors.basebehavior import Behavior
from autobrowser.util.netidle import monitor

if TYPE_CHECKING:
    from autobrowser.basebrowser import BaseAutoBrowser  # noqa: F401

__all__ = ["BaseAutoTab"]

logger = logging.getLogger("autobrowser")


class BaseAutoTab(EventEmitter, metaclass=ABCMeta):
    """Base Automation Tab Class that represents a browser tab in a running browser"""

    def __init__(self, browser: "BaseAutoBrowser", tab_data: Dict[str, str]) -> None:
        super().__init__(loop=asyncio.get_event_loop())
        self.browser: "BaseAutoBrowser" = browser
        self.tab_data: Dict[str, str] = tab_data
        self._url: str = self.tab_data["url"]
        self._id: str = self.tab_data["id"]
        self.client: Client = None
        self._behaviors_paused: bool = False
        self._running: bool = False
        self._reconnecting: bool = False
        self._reconnect_promise: Optional[Future] = None

        self.behaviors: List[Behavior] = []
        self.all_behaviors: Optional[Future] = None
        self.target_info: Optional[Dict] = None

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

    def pause_behaviors(self) -> None:
        """Sets the behaviors paused flag to true"""
        self._behaviors_paused = True

    def resume_behaviors(self) -> None:
        """Sets the behaviors paused flag to false"""
        self._behaviors_paused = False

    async def wait_for_reconnect(self) -> None:
        """If the client connection has been disconnected and we are
        reconnecting, waits for reconnection to happen"""
        if not self.reconnecting or self._reconnect_promise is None:
            return
        if self._reconnect_promise.done():
            return
        await self._reconnect_promise

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
            self._reconnect_promise = asyncio.ensure_future(self._wait_for_reconnect())

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
        if self._reconnect_promise:
            self._reconnect_promise.set_result(True)

    def add_behavior(self, behavior: Behavior) -> None:
        """A Page behavior to the list of behaviors to be run per page

        :param behavior: The behavior to be added
        """
        self.behaviors.append(behavior)

    def net_idle(self, *args: Any, **kwargs: Any) -> Future:
        """Returns a future that  resolves once network idle occurs.

        See the options of autobrowser.util.netidle.monitor for a complete
        description of the available arguments
        """
        return monitor(self.client, *args, **kwargs)

    async def evaluate_in_page(self, js_string: str) -> Dict:
        """Evaluates the supplied string of JavaScript in the tab

        :param js_string: The string of JavaScript to be evaluated
        :return: The results of the evaluation if any
        """
        return await self.client.Runtime.evaluate(
            js_string, userGesture=True, awaitPromise=True, includeCommandLineAPI=True
        )

    async def goto(self, url: str, **kwargs: Any) -> Dict:
        """Initiates browser navigation to the supplied url.

        See cripy.protocol.Page for more information about additional
        arguments or https://chromedevtools.github.io/devtools-protocol/tot/Page#method-navigate

        :param url: The URL to be navigated to
        :param kwargs: Additional arguments to Page.navigate
        :return: The information returned by Page.navigate
        """
        return await self.client.Page.navigate(url, **kwargs)

    @classmethod
    @abstractmethod
    def create(cls, *args: Any, **kwargs: Any) -> "BaseAutoTab":
        """Abstract method for creating new instances of a tab.

        Subclasses are expected to supply the means for creating
        themselves their implementation
        """
        pass

    @abstractmethod
    async def init(self) -> None:
        """Initialize the client connection to the tab.

        Subclasses are expected to call this method from their
        implementation. This can be the only call in their
        implementation.
        """
        if self._running:
            return
        logger.debug("BaseAutoTab.init")
        self._running = True
        self.client = await connect(self.tab_data["webSocketDebuggerUrl"], remote=True)

        logger.debug("BaseAutoTab.init connected")

        self.client.set_close_callback(lambda: self.emit("connection-closed"))

        self.client.Inspector.detached(self.devtools_reconnect)
        self.client.Inspector.targetCrashed(lambda: self.emit("target-crashed"))

        await asyncio.gather(
            self.client.Page.enable(),
            self.client.Network.enable(),
            self.client.Runtime.enable(),
        )

        logger.debug("BaseAutoTab.init enabled domains")

    @abstractmethod
    async def close(self) -> None:
        """Close the client connection to the tab.

        Subclasses are expected to call this method from their
        implementation. This can be the only call in their
        implementation.
        """
        if self.reconnecting:
            self.stop_reconnecting()
        if self.client:
            await self.client.dispose()
            self.client = None
        self._running = False

    def __repr__(self):
        return f"BaseAutoTab({self.tab_data})"
