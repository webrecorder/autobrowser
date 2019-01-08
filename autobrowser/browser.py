import asyncio
import logging
from asyncio import AbstractEventLoop
from typing import ClassVar, Dict, List, Optional

import attr
from pyee import EventEmitter
from redis import Redis

from autobrowser.automation import (
    AutomationInfo,
    BrowserExitInfo,
    TabClosedInfo,
    CloseReason,
)
from .tabs import create_tab, Tab
from .util.helper import Helper

__all__ = ["Browser"]

logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True, frozen=True)
class BrowserEvents(object):
    """The events emitted by browser instances"""
    Exiting: str = attr.ib(default="Browser:Exit")


class Browser(EventEmitter):
    """The Browser class represents a remote Chrome browser and N tabs"""

    Events: ClassVar[BrowserEvents] = BrowserEvents()

    def __init__(
        self,
        info: AutomationInfo,
        loop: Optional[AbstractEventLoop] = None,
        redis: Optional[Redis] = None,
    ) -> None:
        """
        :param info: The information concerning the automation
        :param loop: Optional reference to the running event loop
        :param redis: Optional instance of redis to use
        """
        super().__init__(loop=Helper.ensure_loop(loop))
        self.info: AutomationInfo = info
        self.tab_datas: List[Dict] = None
        self.redis: Optional[Redis] = redis
        self.tabs: Dict[str, Tab] = dict()
        self.tab_closed_reasons: Dict[str, TabClosedInfo] = dict()
        self.running: bool = False

    @property
    def autoid(self) -> str:
        """Retrieve the automation id of the running automation"""
        return self.info.autoid

    @property
    def reqid(self) -> str:
        """Retrieve the request id for this process of the running
        automation"""
        return self.info.reqid

    @property
    def loop(self) -> AbstractEventLoop:
        return self._loop

    async def init(self, tab_datas: Optional[List[Dict]] = None) -> None:
        """Initialize the browser.

        :param tab_datas: List of data about the tabs to be connected to
        """
        self.running = True
        await self._clear_tabs()
        self.tab_closed_reasons.clear()
        if tab_datas is not None:
            self.tab_datas = tab_datas
        for tab_data in self.tab_datas:
            tab = await create_tab(self, tab_data, redis=self.redis)
            self.tabs[tab.tab_id] = tab
            tab.on(Tab.Events.Closed, self._tab_closed)
        await asyncio.sleep(0)

    async def reinit(self, tab_data: Optional[List[Dict]] = None) -> None:
        """Re initialize the browser, if the browser was previously running
        this is an no-op.

        :param tab_data: List of data about the tabs to be connected to
        """
        if self.running:
            return
        logger.info(f"Browser[reinit]: autoid = {self.info.autoid}")
        await self.init(tab_data)

    async def close(self, gracefully: bool = False) -> None:
        """Initiate the close of the browser either gracefully or forcefully.

        Once all tabs have been closed the `Exiting` event is emitted
        with the browsers exit info.

        :param gracefully: A boolean indicating if we should close the
        tabs gracefully or not.
        """
        logger.info(f"Browser[close(gracefully={gracefully})]: initiating close")
        self.running = False
        await self._clear_tabs(gracefully)
        logger.info(f"Browser[close(gracefully={gracefully})]: closed")
        self.emit(
            Browser.Events.Exiting,
            BrowserExitInfo(self.info, list(self.tab_closed_reasons.values())),
        )

    async def shutdown_gracefully(self) -> None:
        """Initiate the graceful closing of the browser and its tabs"""
        if not self.running:
            return
        logger.info("Browser[shutdown_gracefully]: shutting down")
        await self.close(gracefully=True)

    async def _tab_closed(self, info: TabClosedInfo) -> None:
        """Listener registered to the Tab Closed event

        :param info: The closed info for the tab that closed
        """
        logger.info(f"Browser[_tab_closed]: {info}")
        tab = self.tabs.pop(info.tab_id, None)
        if tab is None:
            logger.info(
                f"Browser[_tab_closed]: Tab(tab_id={tab.tab_id}) already removed"
            )
            return
        logger.info(f"Browser[_tab_closed]: removing Tab(tab_id={tab.tab_id})")
        self.tab_closed_reasons[tab.tab_id] = info
        tab.remove_listener(Tab.Events.Closed, self._tab_closed)
        if len(self.tabs) == 0:
            await self.close()

    async def _clear_tabs(self, close_gracefully: bool = False) -> None:
        """Shuts down and remove all tabs for the browser and adds
        their exit info the the `tab_closed_reasons` dictionary.

        :param close_gracefully: A boolean indicating if the the
        tabs should be closed gracefully or forcefully
        """
        for tab in self.tabs.values():
            tab.remove_listener(Tab.Events.Closed, self._tab_closed)
            if close_gracefully:
                await tab.shutdown_gracefully()
                self.tab_closed_reasons[tab.tab_id] = TabClosedInfo(
                    tab.tab_id, CloseReason.GRACEFULLY
                )
            else:
                await tab.close()
                self.tab_closed_reasons[tab.tab_id] = TabClosedInfo(
                    tab.tab_id, CloseReason.CLOSED
                )
        self.tabs.clear()

    def __str__(self) -> str:
        return f"Browser(info={self.info}, tabs={self.tabs}, running={self.running})"

    def __repr__(self) -> str:
        return self.__str__()
