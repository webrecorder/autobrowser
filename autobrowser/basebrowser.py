# -*- coding: utf-8 -*-
import asyncio
import logging
import ujson
from asyncio import AbstractEventLoop
from typing import Optional, List, Dict, Any, Union, ClassVar, Callable

from aiohttp import ClientSession
from pyee import EventEmitter
from redis import Redis

from .tabs import TAB_CLASSES, BaseAutoTab
from .util.shutdown import ShutdownCondition

__all__ = ["BaseAutoBrowser", "DynamicBrowser"]

logger = logging.getLogger("autobrowser")


class AutoBrowserError(Exception):
    pass


class BaseAutoBrowser(EventEmitter):
    CDP_JSON: ClassVar[str] = "http://{ip}:9222/json"
    CDP_JSON_NEW: ClassVar[str] = "http://{ip}:9222/json/new"
    WAIT_TIME: ClassVar[float] = 0.5

    def __init__(
        self,
        browser_id: str = "chrome:67",
        autoid: str = None,
        cdata=None,
        num_tabs: int = 1,
        pubsub: bool = False,
        tab_class: str = "BehaviorTab",
        tab_opts=None,
        loop: Optional[AbstractEventLoop] = None,
        redis: Optional[Redis] = None,
        sd_condition: Optional[ShutdownCondition] = None,
    ) -> None:
        super().__init__(loop=loop if loop is not None else asyncio.get_event_loop())
        self.browser_id = browser_id
        self.cdata = cdata
        self.autoid = autoid
        self.ip: Optional[str] = None
        self.tabs: List[BaseAutoTab] = []
        self.num_tabs = num_tabs
        self.pubsub = pubsub
        self._using_tab: str = tab_class
        self.tab_class = TAB_CLASSES[tab_class]
        self.tab_opts = tab_opts if tab_opts is not None else {}
        self.running = False
        self.redis = redis
        self.sd_condition = sd_condition

    @property
    def loop(self) -> AbstractEventLoop:
        return self._loop

    async def init(self, ip: str) -> None:
        tab_datas = await self.wait_for_tabs(ip)
        self.ip = ip
        self.tabs.clear()
        for tab_data in tab_datas:
            tab = self.tab_class.create(
                self,
                tab_data,
                self.autoid,
                redis=self.redis,
                sd_condition=self.sd_condition,
                **self.tab_opts,
            )
            await tab.init()
            self.tabs.append(tab)

        # self.emit("browser_added", reqid)

    async def close(self) -> None:
        self.running = False

        if self.autoid:
            self.emit("browser_removed", self.autoid)

        for tab in self.tabs:
            await tab.close()

        self.autoid = None

    async def shutdown_gracefully(self) -> None:
        self.running = False
        for tab in self.tabs:
            await tab.shutdown_gracefully()
        self.autoid = None
        self.tabs.clear()

    async def find_browser_tabs(
        self, ip: str, url: Optional[str] = None, require_ws: Optional[bool] = True
    ) -> List[Dict[str, str]]:
        async with ClientSession(json_serialize=ujson.dumps) as session:
            try:
                res = await session.get(self.CDP_JSON.format(ip=ip))
                tabs = await res.json()
            except Exception as e:
                logger.info(str(e))
                return []

        filtered_tabs = []

        for tab in tabs:
            logger.debug("Tab: " + str(tab))

            if require_ws and "webSocketDebuggerUrl" not in tab:
                continue

            if tab.get("type") == "page" and (not url or url == tab["url"]):
                filtered_tabs.append(tab)

        return filtered_tabs

    async def wait_for_tabs(self, ip):
        # wait to find first tab
        while True:
            tab_datas = await self.find_browser_tabs(ip)
            if tab_datas:
                logger.debug(str(tab_datas))
                break

            await asyncio.sleep(self.WAIT_TIME)
            logger.debug("Waiting for first tab")

        # add other tabs
        for _ in range(self.num_tabs - 1):
            tab_data = await self.add_browser_tab(ip)
            tab_datas.append(tab_data)

        return tab_datas

    async def add_browser_tab(self, ip: str) -> Optional[Dict[str, str]]:
        try:
            async with ClientSession(json_serialize=ujson.dumps) as session:
                res = await session.get(self.CDP_JSON_NEW.format(ip=ip))
                return await res.json()
        except Exception as e:
            logger.error("*** " + str(e))

        return None


class DynamicBrowser(BaseAutoBrowser):
    REQ_BROWSER_URL: ClassVar[str] = "/request_browser/{browser}"
    INIT_BROWSER_URL: ClassVar[str] = "/init_browser?reqid={reqid}"
    GET_BROWSER_INFO_URL: ClassVar[str] = "/info/{reqid}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_host = kwargs.pop("api_host", "")
        self.reqid = None
        self.base_ip_url = f"{self.api_host}{self.GET_BROWSER_INFO_URL}"

    async def init(self, reqid: Optional[str] = None) -> None:
        logger.info("DynamicBrowser[init]: initializing")
        tab_datas = None
        ip = None

        # attempt to connect to existing browser/tab
        if reqid is not None:
            ip = await self.get_ip_for_reqid(reqid)

        print("IP", ip)

        if ip is not None:
            tab_datas = await self.wait_for_tabs(ip)

        print("TAB_DATAS", tab_datas)

        # no tab found, init new browser
        if tab_datas is None:

            # ensure reqid is removed
            if reqid is not None:
                self.emit("browser_removed", reqid)

            results = await self.init_new_browser()
            if results is not None:
                reqid = results["reqid"]
                ip = results["ip"]
                tab_datas = results["tab_datas"]

                self.running = True

        self.reqid = reqid
        self.ip = ip
        self.tabs.clear()
        for tab_data in tab_datas:
            tab = self.tab_class.create(
                self,
                tab_data,
                self.autoid,
                redis=self.redis,
                sd_condition=self.sd_condition,
                **self.tab_opts,
            )
            await tab.init()
            self.tabs.append(tab)

        self.emit("browser_added", reqid)

    async def reinit(self):
        if self.running:
            return
        logger.info(f"DynamicBrowser[reinit]: autoid = {self.autoid}")

        await self.init()

    async def get_ip_for_reqid(self, reqid: str) -> Optional[str]:
        """Retrieve the ip address associated with a requests id

        :param reqid: The request id to retrieve the ip address for
        :return: The ip address associated with the request id if it exists
        """
        logger.info(
            f"DynamicBrowser[get_ip_for_reqid]: reqid = {reqid}, autoid = {self.autoid}"
        )

        async with ClientSession(json_serialize=ujson.dumps) as session:
            try:
                res = await session.get(self.base_ip_url.format(reqid=reqid))
                json = await res.json()
                return json.get("ip")
            except Exception:
                pass
        return None

    async def init_new_browser(
        self
    ) -> Optional[Dict[str, Union[str, List[Dict[str, str]]]]]:
        reqid = await self.stage_new_browser(self.browser_id, self.cdata)
        logger.info(
            f"DynamicBrowser[init_new_browser]: reqid = {reqid}, autoid = {self.autoid}"
        )

        # wait for browser init
        async with ClientSession(json_serialize=ujson.dumps) as session:
            while True:
                response = await session.get(
                    self.api_host + self.INIT_BROWSER_URL.format(reqid=reqid),
                    headers={"Host": "localhost"},
                )

                try:
                    res = await response.json()  # type: Dict[str, str]
                except Exception as e:
                    logger.info(
                        f"DynamicBrowser[init_new_browser]: Browser Init Failed {str(e)}"
                    )
                    return None

                if "cmd_port" in res:
                    break

                logger.info("Waiting for Browser: " + str(res))
                await asyncio.sleep(self.WAIT_TIME)

        logger.info(f"DynamicBrowser[init_new_browser]: Launched {str(res)}")

        tab_datas = await self.wait_for_tabs(res.get("ip"))
        logger.info(f"DynamicBrowser[init_new_browser]: got tab datas {tab_datas}")

        return {"ip": res.get("ip"), "reqid": reqid, "tab_datas": tab_datas}

    async def stage_new_browser(
        self, browser_id: str, data: Any
    ) -> Union[str, Dict[str, str]]:
        try:
            async with ClientSession(json_serialize=ujson.dumps) as session:
                req_url = self.REQ_BROWSER_URL.format(browser=browser_id)
                res = await session.post(self.api_host + req_url, data=data)
                json = await res.json()  # type: Dict[str, str]
        except Exception as e:
            logger.debug(str(e))
            return {"error": "not_available"}

        reqid = json.get("reqid")

        if reqid is None:
            return {"error": "not_inited", "browser_id": browser_id}

        return reqid
