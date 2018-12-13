# -*- coding: utf-8 -*-
import asyncio
import logging
from asyncio import AbstractEventLoop
from typing import Optional, List, Dict, ClassVar

import attr
from pyee import EventEmitter
from redis import Redis

from autobrowser.automation import AutomationInfo
from autobrowser.automation.shutdown import ShutdownCondition
from .tabs import create_tab, Tab

__all__ = ["Browser"]

logger = logging.getLogger("autobrowser")


@attr.dataclass(frozen=True)
class BrowserEvents(object):
    Exiting: str = attr.ib(default="Browser:Exit")


@attr.dataclass(slots=True, cmp=False)
class Browser(EventEmitter):
    info: AutomationInfo = attr.ib(default=None)
    loop: AbstractEventLoop = attr.ib(factory=asyncio.get_event_loop, repr=False)
    tab_datas: List[Dict] = attr.ib(default=None)
    redis: Optional[Redis] = attr.ib(default=None, repr=False)
    sd_condition: Optional[ShutdownCondition] = attr.ib(default=None, repr=False)
    tabs: Dict[str, Tab] = attr.ib(factory=dict, repr=False)
    running: bool = attr.ib(init=False, default=False)

    Events: ClassVar[BrowserEvents] = BrowserEvents()

    @property
    def autoid(self) -> str:
        return self.info.autoid

    @property
    def reqid(self) -> str:
        return self.info.reqid

    async def init(self, tab_datas: Optional[List[Dict]] = None) -> None:
        self.running = True
        self.tabs.clear()
        if tab_datas is not None:
            self.tab_datas = tab_datas
        for tab_data in self.tab_datas:
            tab = await create_tab(self, tab_data, redis=self.redis)
            self.tabs[tab.tab_id] = tab
            tab.on(Tab.Events.Crashed, self._tab_crashed_or_connection_closed)
            tab.on(Tab.Events.ConnectionClosed, self._tab_crashed_or_connection_closed)

    async def reinit(self, tab_data: Optional[List[Dict]] = None) -> None:
        if self.running:
            return
        logger.info(f"Browser[reinit]: autoid = {self.info.autoid}")
        await self.init(tab_data)

    async def close(self, gracefully: bool = False) -> None:
        logger.info(f"Browser[close(gracefully={gracefully})]: initiating close")
        self.running = False
        for tab in self.tabs.values():
            if gracefully:
                await tab.shutdown_gracefully()
            else:
                await tab.close()
        self.tabs.clear()
        if not gracefully:
            self.emit(self.Events.Exiting, self.info)
        logger.info(f"Browser[close(gracefully={gracefully})]: closed")

    async def shutdown_gracefully(self) -> None:
        if not self.running:
            return
        logger.info("Browser[shutdown_gracefully]: shutting down")
        await self.close(gracefully=True)
        self.remove_all_listeners()
        logger.info("Browser[shutdown_gracefully]: shutdown complete")

    async def _tab_crashed_or_connection_closed(self, tab_id: str) -> None:
        logger.critical(
            f"Browser[_tab_crashed_or_connection_closed(tab_id={tab_id})]: "
            f"A tab has crashed or the connection to it has closed"
        )
        if tab_id not in self.tabs:
            return
        tab = self.tabs[tab_id]
        await tab.close()
        del self.tabs[tab_id]
        if len(self.tabs) == 0:
            await self.close()

    def __attrs_post_init__(self) -> None:
        super().__init__(loop=self.loop)
