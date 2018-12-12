# -*- coding: utf-8 -*-
import asyncio
import logging
from asyncio import AbstractEventLoop
from typing import Optional, List, Dict

import attr
from redis import Redis

from autobrowser.automation import AutomationInfo
from autobrowser.automation.shutdown import ShutdownCondition
from .tabs import create_tab, Tab

__all__ = ["Browser"]

logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True)
class Browser(object):
    info: AutomationInfo = attr.ib(default=None)
    loop: AbstractEventLoop = attr.ib(factory=asyncio.get_event_loop, repr=False)
    tab_datas: List[Dict] = attr.ib(default=None)
    redis: Optional[Redis] = attr.ib(default=None, repr=False)
    sd_condition: Optional[ShutdownCondition] = attr.ib(default=None, repr=False)
    tabs: List[Tab] = attr.ib(factory=list, repr=False)
    running: bool = attr.ib(init=False, default=False)

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
            self.tabs.append(tab)

    async def reinit(self, tab_data: Optional[List[Dict]] = None) -> None:
        if self.running:
            return
        logger.info(f"Browser[reinit]: autoid = {self.info.autoid}")
        await self.init(tab_data)

    async def close(self, gracefully: bool = False) -> None:
        self.running = False
        for tab in self.tabs:
            if gracefully:
                await tab.shutdown_gracefully()
            else:
                await tab.close()
        self.tabs.clear()

    async def shutdown_gracefully(self) -> None:
        await self.close(gracefully=True)


