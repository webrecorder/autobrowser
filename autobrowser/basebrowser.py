# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Optional, List, Dict, Tuple, Any, Union

from aiohttp import ClientSession
from pyee import EventEmitter

from .behaviors.scroll import AutoScrollBehavior
from .tabs import TAB_CLASSES, BaseAutoTab

__all__ = ["BaseAutoBrowser"]

logger = logging.getLogger("autobrowser")


class AutoBrowserError(Exception):
    pass


class BaseAutoBrowser(EventEmitter):
    CDP_JSON: str = "http://{ip}:9222/json"
    CDP_JSON_NEW: str = "http://{ip}:9222/json/new"

    REQ_BROWSER_URL: str = "/request_browser/{browser}"
    INIT_BROWSER_URL: str = "/init_browser?reqid={reqid}"
    GET_BROWSER_INFO_URL: str = "/info/{reqid}"

    WAIT_TIME: float = 0.5

    def __init__(
        self,
        api_host: str,
        browser_id: str = "chrome:67",
        reqid: str = None,
        cdata=None,
        num_tabs: int = 1,
        pubsub: bool = False,
        tab_class: str = 'BehaviorTab',
        tab_opts=None,
        loop=None,
    ) -> None:
        super().__init__(loop=loop if loop is not None else asyncio.get_event_loop())
        self.api_host = api_host
        self.browser_id = browser_id
        self.cdata = cdata
        self.reqid = reqid
        self.ip: Optional[str] = None
        self.tabs: List[BaseAutoTab] = []
        self.num_tabs = num_tabs
        self.pubsub = pubsub
        self.tab_class = TAB_CLASSES[tab_class]
        self.tab_opts = tab_opts if tab_opts is not None else {}
        self.base_ip_url = f"{self.api_host}{self.GET_BROWSER_INFO_URL}"
        self.running = False

    async def init(self, reqid: Optional[str] = None) -> None:
        ip = None
        tab_datas = None

        # attempt to connect to existing browser/tab
        if reqid is not None:
            ip = await self.get_ip_for_reqid(reqid)
            if ip is not None:
                tab_datas = await self.find_browser_tabs(ip)

            # ensure reqid is removed
            if tab_datas is None:
                self.emit("browser_removed", reqid)

        # no tab found, init new browser
        if tab_datas is None:
            reqid, ip, tab_datas = await self.init_new_browser()

        self.reqid = reqid
        self.ip = ip
        self.tabs.clear()
        for tab_data in tab_datas:
            tab = self.tab_class.create(self, tab_data, **self.tab_opts)
            await tab.init()
            self.tabs.append(tab)

        self.emit("browser_added", reqid)

    async def reinit(self):
        if self.running:
            return

        await self.init()

        logger.debug("Auto Browser Re-Inited: " + self.reqid)

    async def close(self) -> None:
        self.running = False

        if self.reqid:
            self.emit("browser_removed", self.reqid)

        for tab in self.tabs:
            await tab.close()

        self.reqid = None

    async def get_ip_for_reqid(self, reqid: str) -> Optional[str]:
        """Retrieve the ip address associated with a requests id

        :param reqid: The request id to retrieve the ip address for
        :return: The ip address associated with the request id if it exists
        """
        logger.debug(f"BaseAutoBrowser.get_ip_for_reqid({reqid})")

        async with ClientSession() as session:
            try:
                res = await session.get(self.base_ip_url.format(reqid=reqid))
                json = await res.json()
                return json.get("ip")
            except Exception:
                pass
        return None

    async def find_browser_tabs(
        self, ip: str, url: Optional[str] = None, require_ws: Optional[bool] = True
    ) -> List[Dict[str, str]]:
        async with ClientSession() as session:
            try:
                res = await session.get(self.CDP_JSON.format(ip=ip))
                tabs = await res.json()
            except Exception as e:
                logger.debug(str(e))
                return []

        filtered_tabs = []

        for tab in tabs:
            logger.debug("Tab: " + str(tab))

            if require_ws and "webSocketDebuggerUrl" not in tab:
                continue

            if tab.get("type") == "page" and (not url or url == tab["url"]):
                filtered_tabs.append(tab)

        return filtered_tabs

    async def init_new_browser(
        self
    ) -> Tuple[Optional[str], Optional[str], Optional[List[Dict[str, str]]]]:
        reqid = await self.stage_new_browser(self.browser_id, self.cdata)

        # wait for browser init
        async with ClientSession() as session:
            while True:
                res = await session.get(
                    self.api_host + self.INIT_BROWSER_URL.format(reqid=reqid)
                )

                try:
                    res = await res.json()
                except Exception as e:
                    logger.debug("Browser Init Failed: " + str(e))
                    return None, None, None

                if "cmd_port" in res:
                    break

                logger.debug("Waiting for Browser: " + str(res))
                await asyncio.sleep(self.WAIT_TIME)

        logger.debug("Launched: " + str(res))

        self.running = True

        # wait to find first tab
        while True:
            tab_datas = await self.find_browser_tabs(res["ip"])
            if tab_datas:
                logger.debug(str(tab_datas))
                break

            await asyncio.sleep(self.WAIT_TIME)
            logger.debug("Waiting for first tab")

        # add other tabs
        for _ in range(self.num_tabs - 1):
            tab_data = await self.add_browser_tab(res["ip"])
            tab_datas.append(tab_data)

        return reqid, res["ip"], tab_datas

    async def stage_new_browser(
        self, browser_id: str, data: Any
    ) -> Union[str, Dict[str, str]]:
        try:
            async with ClientSession() as session:
                req_url = self.REQ_BROWSER_URL.format(browser=browser_id)
                res = await session.post(self.api_host + req_url, data=data)
                json = await res.json()
        except Exception as e:
            logger.debug(str(e))
            return {"error": "not_available"}

        reqid = json.get("reqid")

        if reqid is None:
            return {"error": "not_inited", "browser_id": browser_id}

        return reqid

    async def add_browser_tab(self, ip: str) -> Optional[Dict[str, str]]:
        tab = None
        try:
            async with ClientSession() as session:
                res = await session.get(self.CDP_JSON_NEW.format(ip=ip))
                tab = await res.json()
        except Exception as e:
            logger.error("*** " + str(e))

        return tab
