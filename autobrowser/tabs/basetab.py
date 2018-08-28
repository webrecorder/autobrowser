# -*- coding: utf-8 -*-
import asyncio
from abc import ABCMeta, abstractmethod
from asyncio import Future
from typing import Optional, Dict, Any
from typing import Type, List

from cripy import Client
from pyee import EventEmitter

from ..basebrowser import BaseAutoBrowser
from ..behaviors.basebehavior import Behavior
from ..util.netidle import monitor

__all__ = ["AutoTabError", "BaseAutoTab"]


class AutoTabError(Exception):
    pass


class BaseAutoTab(EventEmitter, metaclass=ABCMeta):
    """Base Automation Tab Class that represents a browser tab in a running browser"""

    def __init__(
        self, browser: Type[BaseAutoBrowser], tab_data: Dict[str, str]
    ) -> None:
        super().__init__()
        self.browser: BaseAutoBrowser = browser
        self.tab_data: Dict[str, str] = tab_data
        self.client: Optional[Client] = None
        self._running: bool = False
        self._reconnecting: bool = False
        self._reconnect_promise: Optional[Future] = None

        self.behaviors: List[Behavior] = []
        self.all_behaviors: Optional[Future] = None
        self.target_info: Optional[Dict] = None

    @property
    def running(self) -> bool:
        """Is this tab running (active client connection)"""
        return self._running

    @property
    def reconnecting(self) -> bool:
        """Is this tab attempting to reconnect to the tab"""
        return self._running and self._reconnecting

    async def wait_for_reconnect(self) -> None:
        """If the client connection has been disconnected and we are reconnecting, waits for reconnection to happen"""
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
        except:
            pass
        self._reconnecting = False

    def devtools_reconnect(self, result: Dict[str, str]) -> None:
        """Callback used to reconnect to the browser tab when the client connection was replaced with the devtools."""
        if result["reason"] == "replaced_with_devtools":
            self._reconnecting = True
            self._reconnect_promise = asyncio.ensure_future(self._wait_for_reconnect())

    async def _wait_for_reconnect(self) -> None:
        """Attempt to reconnect to browser tab after client connection was replayed with the devtools"""
        while True:
            try:
                await self.init()
                break
            except Exception as e:
                print(e)

            await asyncio.sleep(3.0)
        self._reconnecting = False
        self._reconnect_promise.set_result(True)

    def add_behavior(self, behavior: Behavior) -> None:
        """A Page behavior to the list of behaviors to be run per page

        :param behavior: The behavior to be added
        """
        self.behaviors.append(behavior)

    def net_idle(self) -> Future:
        return monitor(self.client)

    @abstractmethod
    async def init(self):
        """Initialize the client connection to the tab"""
        pass

    @abstractmethod
    async def close(self):
        """Close the client connection to the tab"""
        if self.reconnecting:
            self.stop_reconnecting()
        if self.all_behaviors:
            self.all_behaviors.cancel()
            self.all_behaviors = None
        self._running = False

    @abstractmethod
    async def evaluate_in_page(self, js_string: str):
        pass

    @abstractmethod
    async def goto(self, url: str, options: Optional[Dict] = None, **kwargs: Any):
        pass

    def __repr__(self):
        return f"BaseAutoTab({self.tab_data})"
