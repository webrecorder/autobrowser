import asyncio
import logging
import os
import ujson
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop, Task, CancelledError
from typing import Optional, List, Dict, Any, Union

import aioredis
from aiohttp import ClientSession
from aioredis import Redis, Channel

from autobrowser.browser import Browser
from autobrowser.automation.details import AutomationInfo, AutomationConfig
from autobrowser.automation.shutdown import ShutdownCondition
from autobrowser.errors import BrowserStagingError

CDP_JSON: str = "http://{ip}:9222/json"
CDP_JSON_NEW: str = "http://{ip}:9222/json/new"
REQ_BROWSER_URL: str = "/request_browser/{browser}"
INIT_BROWSER_URL: str = "/init_browser?reqid={reqid}"
GET_BROWSER_INFO_URL: str = "/info/{reqid}"
WAIT_TIME: float = 0.5

logger = logging.getLogger("autobrowser")


class Driver(ABC):
    @abstractmethod
    async def init(self) -> None:
        pass

    @abstractmethod
    async def run(self) -> None:
        pass


class ShepardDriver(Driver, ABC):
    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        self.conf: AutomationConfig = conf
        self.loop: AbstractEventLoop = loop if loop is not None else asyncio.get_event_loop()
        self.browser_info_url: str = self.conf.api_host + GET_BROWSER_INFO_URL
        self.request_new_browser_url: str = self.conf.api_host + REQ_BROWSER_URL
        self.init_browser_url: str = self.conf.api_host + INIT_BROWSER_URL
        self.session: ClientSession = ClientSession(
            json_serialize=ujson.dumps, loop=self.loop
        )

    async def stage_new_browser(
        self, browser_id: str, data: Optional[Any] = None
    ) -> str:
        response = await self.session.post(
            self.request_new_browser_url.format(browser=browser_id), data=data
        )
        json = await response.json()
        reqid = json.get("reqid")
        if reqid is None:
            raise BrowserStagingError(f"Could not stage browser with id = {browser_id}")
        return reqid

    async def init_new_browser(
        self, browser_id: str, data: Optional[Any] = None
    ) -> Optional[Dict[str, Union[str, List[Dict[str, str]]]]]:
        reqid = await self.stage_new_browser(browser_id, data)
        while True:
            response = await self.session.get(
                self.init_browser_url.format(reqid=reqid),
                headers=dict(Host="localhost"),
            )
            try:
                data = await response.json()
            except Exception as e:
                logger.info(
                    f"BrowserRequests[init_new_browser]: Browser Init Failed {str(e)}"
                )
                return None
            if "cmd_port" in data:
                break
            logger.info(
                "BrowserRequests[init_new_browser]: Waiting for Browser: " + str(data)
            )
            await asyncio.sleep(WAIT_TIME, loop=self.loop)
        tab_datas = await self.wait_for_tabs(data.get("ip"), self.conf.num_tabs)
        return dict(ip=data.get("ip"), reqid=reqid, tab_datas=tab_datas)

    async def wait_for_tabs(self, ip: str, num_tabs: int = 0) -> List[Dict[str, str]]:
        while True:
            tab_datas = await self.find_browser_tabs(ip=ip)
            if tab_datas:
                break
            logger.debug(
                f"BrowserRequests[wait_for_tabs(ip={ip}, num_tabs={num_tabs})]: Waiting for first tab"
            )
            await asyncio.sleep(WAIT_TIME, loop=self.loop)
        if num_tabs > 0:
            for _ in range(num_tabs - 1):
                tab_data = await self.create_browser_tab(ip)
                tab_datas.append(tab_data)
        return tab_datas

    async def find_browser_tabs(
        self,
        ip: Optional[str] = None,
        url: Optional[str] = None,
        require_ws: Optional[bool] = True,
    ) -> List[Dict[str, str]]:
        filtered_tabs: List[Dict[str, str]] = []
        try:
            res = await self.session.get(CDP_JSON.format(ip=ip))
            tabs = await res.json()
        except Exception as e:
            logger.info(str(e))
            return filtered_tabs

        for tab in tabs:
            logger.debug("Tab: " + str(tab))

            if require_ws and "webSocketDebuggerUrl" not in tab:
                continue

            if tab.get("type") == "page" and (not url or url == tab["url"]):
                filtered_tabs.append(tab)

        return filtered_tabs

    async def get_ip_for_reqid(self, reqid: str) -> Optional[str]:
        """Retrieve the ip address associated with a requests id

        :param reqid: The request id to retrieve the ip address for
        :return: The ip address associated with the request id if it exists
        """
        logger.info(
            f"Shepard[get_ip_for_reqid(reqid={reqid})]: Retrieving the ip associated with the reqid"
        )
        try:
            res = await self.session.get(self.browser_info_url.format(reqid=reqid))
            json = await res.json()
            return json.get("ip")
        except Exception:
            pass
        return None

    async def create_browser_tab(self, ip: str) -> Dict[str, str]:
        res = await self.session.get(CDP_JSON_NEW.format(ip=ip))
        return await res.json()


class SingleBrowserDriver(ShepardDriver):
    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.redis: Redis = None
        self.shutdown_condition: ShutdownCondition = ShutdownCondition(self.loop)
        self.browser: Browser = None

    async def init(self) -> None:
        logger.info("SingleBrowserDriver[run]: started")
        redis_url = os.environ.get("REDIS_URL", "redis://localhost")
        print("REDIS", redis_url)
        self.redis = await aioredis.create_redis(
            redis_url, loop=self.loop, encoding="utf-8"
        )

    async def run(self) -> None:
        await self.init()
        tab_datas = await self.wait_for_tabs(
            self.conf.browser_host_ip, self.conf.num_tabs
        )
        self.browser = Browser(
            info=AutomationInfo(autoid=self.conf.autoid, tab_type=self.conf.tab_type),
            loop=self.loop,
            redis=self.redis,
            sd_condition=self.shutdown_condition,
        )
        await self.browser.init(tab_datas)
        logger.info("SingleBrowserDriver[run]: waiting for shutdown")
        await self.shutdown_condition
        await self.browser.shutdown_gracefully()
        await self.session.close()
        self.redis.close()
        await self.redis.wait_closed()


class MultiBrowserDriver(ShepardDriver):
    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.redis: Redis = None
        self.shutdown_condition: ShutdownCondition = ShutdownCondition(self.loop)
        self.browsers: Dict[str, Browser] = dict()
        self.ae_channel: Channel = None
        self.pubsub_task: Task = None

    async def get_auto_event_channel(self) -> Channel:
        channels = await self.redis.subscribe("auto-event")
        return channels[0]

    async def pubsub_loop(self) -> None:
        while await self.ae_channel.wait_message():
            msg = await self.ae_channel.get(encoding="utf-8", decoder=ujson.loads)
            logger.debug(f"pubsub_loop got message {msg}")
            if msg["type"] == "start":
                await self.add_browser(msg["reqid"])
            elif msg["type"] == "stop":
                await self.remove_browser(msg["reqid"])

    async def add_browser(self, reqid) -> None:
        logger.debug("Start Automating Browser: " + reqid)
        browser = self.browsers.get(reqid)
        tab_datas = None
        if not browser:
            # attempt to connect to existing browser/tab
            browser_ip = await self.get_ip_for_reqid(reqid)
            if browser_ip is not None:
                tab_datas = await self.wait_for_tabs(browser_ip)

            if tab_datas is None:
                # no tab found, init new browser
                results = await self.init_new_browser(
                    self.conf.browser_id, self.conf.cdata
                )
                tab_datas = results["tab_datas"]
            browser = Browser(
                info=AutomationInfo(
                    reqid=reqid, autoid=self.conf.autoid, tab_type=self.conf.tab_type
                ),
                loop=self.loop,
                redis=self.redis,
                sd_condition=self.shutdown_condition,
            )
            await browser.init(tab_datas)
            self.browsers[reqid] = browser

    async def remove_browser(self, reqid) -> None:
        logger.debug("Stop Automating Browser: " + reqid)
        browser = self.browsers.get(reqid)
        if not browser:
            return
        await browser.close()
        del self.browsers[reqid]

    async def init(self) -> None:
        logger.info("SingleBrowserDriver[run]: started")
        redis_url = os.environ.get("REDIS_URL", "redis://localhost")
        print("REDIS", redis_url)
        self.redis = await aioredis.create_redis(
            redis_url, loop=self.loop, encoding="utf-8"
        )
        self.ae_channel = await self.get_auto_event_channel()
        self.pubsub_task = self.loop.create_task(self.pubsub_loop())

    async def run(self) -> None:
        logger.info("Driver.run")
        await self.init()
        logger.info("Driver waiting for shutdown")
        await self.shutdown_condition
        self.pubsub_task.cancel()
        try:
            await self.pubsub_task
        except CancelledError:
            pass
        self.ae_channel.close()
        for browser in self.browsers.values():
            await browser.shutdown_gracefully()
        self.browsers.clear()
        self.redis.close()
        await self.redis.wait_closed()
        await self.session.close()
