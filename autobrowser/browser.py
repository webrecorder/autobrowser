# -*- coding: utf-8 -*-
import asyncio
import logging
from asyncio import AbstractEventLoop
from typing import Optional, List

import attr
from redis import Redis

from autobrowser.automation import AutomationInfo, BrowserRequests
from .tabs import create_tab, BaseAutoTab
from autobrowser.automation.shutdown import ShutdownCondition

__all__ = ["Browser", "DynamicBrowser"]

logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True)
class Browser(object):
    browser_req: BrowserRequests = attr.ib(repr=False)
    automation: AutomationInfo = attr.ib(default=None)
    loop: AbstractEventLoop = attr.ib(factory=asyncio.get_event_loop, repr=False)
    redis: Optional[Redis] = attr.ib(default=None, repr=False)
    sd_condition: Optional[ShutdownCondition] = attr.ib(default=None, repr=False)
    tabs: List[BaseAutoTab] = attr.ib(factory=list, repr=False)
    running: bool = attr.ib(init=False, default=False)

    @property
    def autoid(self) -> str:
        return self.automation.autoid

    @property
    def reqid(self) -> str:
        return self.automation.reqid

    async def init(self, info: Optional[AutomationInfo] = None) -> None:
        self.running = True
        self.tabs.clear()
        if info is not None:
            self.automation = info
        tab_datas = await self.browser_req.wait_for_tabs(
            self.automation.ip, num_tabs=self.automation.num_tabs
        )
        for tab_data in tab_datas:
            tab = create_tab(self, tab_data, redis=self.redis)
            await tab.init()
            self.tabs.append(tab)

    async def close(self, gracefully: bool = False) -> None:
        self.running = False
        for tab in self.tabs:
            if gracefully:
                await tab.shutdown_gracefully()
            else:
                await tab.close()
        self.tabs.clear()
        await self.browser_req.close()

    async def shutdown_gracefully(self) -> None:
        await self.close(gracefully=True)


@attr.dataclass(slots=True)
class DynamicBrowser(Browser):
    browser_req: BrowserRequests = attr.ib(repr=False)
    automation: AutomationInfo = attr.ib(default=None)
    loop: AbstractEventLoop = attr.ib(factory=asyncio.get_event_loop, repr=False)
    redis: Optional[Redis] = attr.ib(default=None, repr=False)
    sd_condition: Optional[ShutdownCondition] = attr.ib(default=None, repr=False)

    async def init(self, info: Optional[AutomationInfo] = None) -> None:
        logger.info("DynamicBrowser[init]: initializing")
        self.running = True
        self.tabs.clear()
        if info is not None:
            self.automation = info
        tab_datas = None
        # attempt to connect to existing browser/tab
        if self.automation.reqid is not None:
            self.automation.ip = await self.browser_req.get_ip_for_reqid(
                self.automation.reqid
            )
        if self.automation.ip is not None:
            tab_datas = await self.browser_req.wait_for_tabs(self.automation.ip)
        # no tab found, init new browser
        if tab_datas is None:
            results = await self.browser_req.init_new_browser(
                self.automation.browser_id, self.automation.cdata
            )
            self.automation.reqid = results["reqid"]
            self.automation.ip = results["ip"]
            tab_datas = results["tab_datas"]
        for tab_data in tab_datas:
            tab = create_tab(self, tab_data, redis=self.redis)
            await tab.init()
            self.tabs.append(tab)

    async def reinit(self):
        if self.running:
            return
        logger.info(f"DynamicBrowser[reinit]: autoid = {self.automation.autoid}")

        await self.init()
