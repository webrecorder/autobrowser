import asyncio
import logging
import ujson
from abc import ABC
from asyncio import AbstractEventLoop, Task
from typing import Optional, List, Dict, Any, Union

from aiohttp import ClientSession
from aioredis import Channel

from autobrowser.automation import AutomationConfig, AutomationInfo
from autobrowser.browser import Browser
from autobrowser.errors import BrowserStagingError
from .basedriver import Driver

__all__ = [
    "CDP_JSON",
    "CDP_JSON_NEW",
    "REQ_BROWSER_URL",
    "INIT_BROWSER_URL",
    "GET_BROWSER_INFO_URL",
    "WAIT_TIME",
    "ShepherdDriver",
    "SingleBrowserDriver",
    "MultiBrowserDriver",
]

logger = logging.getLogger("autobrowser")

CDP_JSON: str = "http://{ip}:9222/json"
CDP_JSON_NEW: str = "http://{ip}:9222/json/new"
REQ_BROWSER_URL: str = "/request_browser/{browser}"
INIT_BROWSER_URL: str = "/init_browser?reqid={reqid}"
GET_BROWSER_INFO_URL: str = "/info/{reqid}"
WAIT_TIME: float = 0.5


class ShepherdDriver(Driver, ABC):
    """An abstract base driver class for using browsers managed by shepherd"""
    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.browser_info_url: str = self.conf["api_host"] + GET_BROWSER_INFO_URL
        self.request_new_browser_url: str = self.conf["api_host"] + REQ_BROWSER_URL
        self.init_browser_url: str = self.conf["api_host"] + INIT_BROWSER_URL
        self.session: ClientSession = ClientSession(
            json_serialize=ujson.dumps, loop=self.loop
        )

    async def stage_new_browser(
        self, browser_id: str, data: Optional[Any] = None
    ) -> str:
        response = await self.session.post(
            self.request_new_browser_url.format(browser=browser_id), data=data
        )
        json = await response.json()  # type: Dict[str, str]
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
                    f"{self._class_name}[init_new_browser]: Browser Init Failed {str(e)}"
                )
                return None
            if "cmd_port" in data:
                break
            logger.info(
                f"{self._class_name}[init_new_browser]: Waiting for Browser: "
                + str(data)
            )
            await asyncio.sleep(WAIT_TIME, loop=self.loop)
        tab_datas = await self.wait_for_tabs(data.get("ip"), self.conf["num_tabs"])
        return dict(ip=data.get("ip"), reqid=reqid, tab_datas=tab_datas)

    async def wait_for_tabs(self, ip: str, num_tabs: int = 0) -> List[Dict[str, str]]:
        while True:
            tab_datas = await self.find_browser_tabs(ip=ip)
            if tab_datas:
                break
            logger.debug(
                f"{self._class_name}[wait_for_tabs(ip={ip}, num_tabs={num_tabs})]: Waiting for first tab"
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
            f"{self._class_name}[get_ip_for_reqid(reqid={reqid})]: Retrieving the ip associated with the reqid"
        )
        try:
            res = await self.session.get(self.browser_info_url.format(reqid=reqid))
            json = await res.json()  # type: Dict[str, str]
            return json.get("ip")
        except Exception:
            pass
        return None

    async def create_browser_tab(self, ip: str) -> Dict[str, str]:
        res = await self.session.get(CDP_JSON_NEW.format(ip=ip))
        return await res.json()

    async def clean_up(self) -> None:
        logger.info(f"{self._class_name}[clean_up]: closing client session")
        if self.session is not None:
            await self.session.close()
        await super().clean_up()


class SingleBrowserDriver(ShepherdDriver):
    """A driver for running an automation using a single remote browser"""
    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.browser: Browser = None

    async def init(self) -> None:
        logger.info(f"{self._class_name}[init]: initializing")
        await super().init()

    async def run(self) -> None:
        if not self.did_init:
            await self.init()
        tab_datas = await self.wait_for_tabs(
            self.conf.get("browser_host_ip"), self.conf.get("num_tabs")
        )
        self.browser = Browser(
            info=AutomationInfo(
                autoid=self.conf.get("autoid"), tab_type=self.conf.get("tab_type")
            ),
            loop=self.loop,
            redis=self.redis,
            sd_condition=self.shutdown_condition,
        )
        self.browser.on(Browser.Events.Exiting, self.on_browser_exit)
        await self.browser.init(tab_datas)
        logger.info("SingleBrowserDriver[run]: waiting for shutdown")
        await self.shutdown_condition
        logger.info("SingleBrowserDriver[run]: shutdown condition met")
        await self.shutdown()

    async def shutdown(self) -> None:
        logger.info("SingleBrowserDriver[shutdown]: shutting down")
        if self.browser is not None:
            await self.browser.shutdown_gracefully()
        await super().clean_up()
        logger.info("SingleBrowserDriver[shutdown]: exiting")

    def on_browser_exit(self, info: AutomationInfo) -> None:
        logging.info(f"SingleBrowserDriver[on_browser_exit(info={info})]: The browser exited")
        self.browser.remove_all_listeners()
        self.shutdown_condition.initiate_shutdown()


class MultiBrowserDriver(ShepherdDriver):
    """A driver for running multiple automations via multiple remote browser"""
    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.browsers: Dict[str, Browser] = dict()
        self.ae_channel: Channel = None
        self.pubsub_task: Task = None

    async def get_auto_event_channel(self) -> Channel:
        channels = await self.redis.subscribe("auto-event")
        return channels[0]

    async def pubsub_loop(self) -> None:
        while await self.ae_channel.wait_message():
            msg = await self.ae_channel.get(encoding="utf-8", decoder=ujson.loads)
            logger.debug(f"{self._class_name}[pubsub_loop]: got message {msg}")
            if msg["type"] == "start":
                await self.add_browser(msg["reqid"])
            elif msg["type"] == "stop":
                await self.remove_browser(msg["reqid"])

    async def add_browser(self, reqid) -> None:
        logger.debug(
            f"{self._class_name}[add_browser] Start Automating Browser: " + reqid
        )
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
                    self.conf.get("browser_id"), self.conf.get("cdata")
                )
                tab_datas = results["tab_datas"]
            browser = Browser(
                info=AutomationInfo(
                    reqid=reqid,
                    autoid=self.conf.get("autoid"),
                    tab_type=self.conf.get("tab_type"),
                ),
                loop=self.loop,
                redis=self.redis,
                sd_condition=self.shutdown_condition,
            )
            await browser.init(tab_datas)
            self.browsers[reqid] = browser
            browser.on(Browser.Events.Exiting, self.on_browser_exit)

    async def remove_browser(self, reqid) -> None:
        logger.debug("Stop Automating Browser: " + reqid)
        browser = self.browsers.get(reqid)
        if not browser:
            return
        del self.browsers[reqid]
        await browser.shutdown_gracefully()

    async def init(self) -> None:
        logger.info("MultiBrowserDriver[init]: initializing")
        await super().init()
        self.ae_channel = await self.get_auto_event_channel()
        self.pubsub_task = self.loop.create_task(self.pubsub_loop())

    async def run(self) -> None:
        logger.info("MultiBrowserDriver[run]: running")
        if not self.did_init:
            await self.init()
        logger.info("MultiBrowserDriver[run]: waiting for shutdown")
        await self.shutdown_condition
        logger.info("MultiBrowserDriver[run]: shutdown condition met")
        await self.shutdown()

    async def clean_up(self) -> None:
        logger.info("MultiBrowserDriver[clean_up]: cleaning up")
        self.pubsub_task.cancel()
        try:
            await self.pubsub_task
        except asyncio.CancelledError:
            pass
        self.ae_channel.close()
        await super().clean_up()

    async def shutdown(self) -> None:
        logger.info("MultiBrowserDriver[shutdown]: shutting down")
        for browser in self.browsers.values():
            await browser.shutdown_gracefully()
        self.browsers.clear()
        await self.clean_up()
        logger.info("MultiBrowserDriver[shutdown]: exiting")

    def on_browser_exit(self, info: AutomationInfo) -> None:
        sig = f"MultiBrowserDriver[on_browser_exit(info={info})]"
        logging.info(f"{sig}: the browser exited")
        browser = self.browsers.get(info.reqid)
        if browser is None:
            return
        del self.browsers[info.reqid]
        browser.remove_all_listeners()
        if len(self.browsers) == 0:
            logging.info(f"{sig}: no more active browsers, shutting down")
            self.shutdown_condition.initiate_shutdown()

