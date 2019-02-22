import logging
import ujson
from abc import ABC
from asyncio import AbstractEventLoop, Task, sleep as aio_sleep, CancelledError
from typing import Any, Dict, List, Optional, Union
from ujson import loads as ujson_loads

from aioredis import Channel

from autobrowser.automation import AutomationConfig, AutomationInfo, BrowserExitInfo
from autobrowser.chrome_browser import Chrome
from autobrowser.errors import BrowserStagingError
from autobrowser.util import HTTPGet, HTTPPost, HTTPRequestSession
from .basedriver import BaseDriver

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


class ShepherdDriver(BaseDriver, ABC):
    """An abstract base driver class for using browsers managed by shepherd"""

    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.browser_info_url: str = self.conf["api_host"] + GET_BROWSER_INFO_URL
        self.request_new_browser_url: str = self.conf["api_host"] + REQ_BROWSER_URL
        self.init_browser_url: str = self.conf["api_host"] + INIT_BROWSER_URL
        self.pubsub_channel: Channel = None
        self.pubsub_task: Task = None

    async def stage_new_browser(
        self, browser_id: str, data: Optional[Any] = None
    ) -> str:
        async with self.session.post(
            self.request_new_browser_url.format(browser=browser_id), data=data
        ) as response:
            json = await response.json(loads=ujson_loads)  # type: Dict[str, str]
        reqid = json.get("reqid")
        if reqid is None:
            raise BrowserStagingError(f"Could not stage browser with id = {browser_id}")
        return reqid

    async def init_new_browser(
        self, browser_id: str, data: Optional[Any] = None
    ) -> Optional[Dict[str, Union[str, List[Dict[str, str]]]]]:
        reqid = await self.stage_new_browser(browser_id, data)
        while 1:
            async with self.session.get(
                self.init_browser_url.format(reqid=reqid),
                headers=dict(Host="localhost"),
            ) as response:
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
                await aio_sleep(WAIT_TIME, loop=self.loop)
        tab_datas = await self.wait_for_tabs(data.get("ip"), self.conf["num_tabs"])
        return dict(ip=data.get("ip"), reqid=reqid, tab_datas=tab_datas)

    async def wait_for_tabs(self, ip: str, num_tabs: int = 0) -> List[Dict[str, str]]:
        while 1:
            tab_datas = await self.find_browser_tabs(ip=ip)
            if tab_datas:
                break
            logger.debug(
                f"{self._class_name}[wait_for_tabs(ip={ip}, num_tabs={num_tabs})]: Waiting for first tab"
            )
            await aio_sleep(WAIT_TIME, loop=self.loop)
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
            async with self.session.get(CDP_JSON.format(ip=ip)) as res:
                tabs = await res.json(loads=ujson_loads)
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
            async with self.session.get(
                self.browser_info_url.format(reqid=reqid)
            ) as res:
                json = await res.json(loads=ujson_loads)  # type: Dict[str, str]
                return json.get("ip")
        except Exception:
            pass
        return None

    async def create_browser_tab(self, ip: str) -> Dict[str, str]:
        async with self.session.get(CDP_JSON_NEW.format(ip=ip)) as res:
            return await res.json(loads=ujson_loads)

    async def clean_up(self) -> None:
        logger.info(f"{self._class_name}[clean_up]: closing redis connection")
        if self.pubsub_task and not self.pubsub_task.done():
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except CancelledError:
                pass
            self.pubsub_task = None
        if self.pubsub_channel is not None:
            self.pubsub_channel.close()
        await super().clean_up()


class SingleBrowserDriver(ShepherdDriver):
    """A driver for running an automation using a single remote browser"""

    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.browser: Chrome = None

    async def init(self) -> None:
        logger.info(f"{self._class_name}[init]: initializing")
        await super().init()
        tab_datas = await self.wait_for_tabs(
            self.conf.get("browser_host_ip"), self.conf.get("num_tabs")
        )
        self.browser = Chrome(
            info=AutomationInfo(
                autoid=self.conf.get("autoid"),
                tab_type=self.conf.get("tab_type"),
                reqid=self.conf.get("reqid", ""),
                behavior_manager=self.behavior_manager,
            ),
            loop=self.loop,
            redis=self.redis,
        )
        self.browser.on(Chrome.Events.Exiting, self.on_browser_exit)
        await self.browser.init(tab_datas)
        self.pubsub_task = self.loop.create_task(self.pubsub_loop())

    async def get_auto_event_channel(self) -> Channel:
        channels = await self.redis.subscribe(
            "wr.auto-event:{reqid}".format(reqid=self.conf.get("reqid", ""))
        )
        return channels[0]

    async def pubsub_loop(self) -> None:
        self.pubsub_channel = await self.get_auto_event_channel()
        logger.debug("SingleBrowserDriver[pubsub_loop]: started")
        while await self.pubsub_channel.wait_message():
            msg = await self.pubsub_channel.get(encoding="utf-8", decoder=ujson.loads)
            logger.debug(f"{self._class_name}[pubsub_loop]: got message {msg}")

            if msg["cmd"] == "stop":
                for tab in self.browser.tabs.values():
                    await tab.pause_behaviors()

            elif msg["cmd"] == "start":
                for tab in self.browser.tabs.values():
                    await tab.resume_behaviors()

            elif msg["cmd"] == "shutdown":
                self.shutdown_condition.initiate_shutdown()
            logger.debug(
                f"{self._class_name}[pubsub_loop]: waiting for another message"
            )
        logger.debug("SingleBrowserDriver[pubsub_loop]: stopped")

    async def shutdown(self) -> int:
        logger.info("SingleBrowserDriver[shutdown]: shutting down")
        if self.browser is not None:
            await self.gracefully_shutdown_browser(self.browser)
            self.browser = None
        await super().clean_up()
        logger.info("SingleBrowserDriver[shutdown]: exiting")
        return self.determine_exit_code()

    def on_browser_exit(self, info: BrowserExitInfo) -> None:
        logging.info(
            f"SingleBrowserDriver[on_browser_exit(info={info})]: The browser exited"
        )
        self._browser_exit_infos.append(info)
        self.browser.remove_all_listeners()
        self.browser = None
        self.shutdown_condition.initiate_shutdown()


class MultiBrowserDriver(ShepherdDriver):
    """A driver for running multiple automations via multiple remote browser"""

    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.browsers: Dict[str, Chrome] = dict()

    async def get_auto_event_channel(self) -> Channel:
        channels = await self.redis.subscribe("auto-event")
        return channels[0]

    async def pubsub_loop(self) -> None:
        while await self.pubsub_channel.wait_message():
            msg = await self.pubsub_channel.get(encoding="utf-8", decoder=ujson.loads)
            logger.debug(f"{self._class_name}[pubsub_loop]: got message {msg}")
            if msg["cmd"] == "start":
                await self.add_browser(msg["reqid"])
            elif msg["cmd"] == "stop":
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

            browser = Chrome(
                info=AutomationInfo(
                    reqid=reqid,
                    autoid=self.conf.get("autoid"),
                    tab_type=self.conf.get("tab_type"),
                    behavior_manager=self.behavior_manager,
                ),
                loop=self.loop,
                redis=self.redis,
            )

            await browser.init(tab_datas)
            self.browsers[reqid] = browser
            browser.on(Chrome.Events.Exiting, self.on_browser_exit)

    async def remove_browser(self, reqid) -> None:
        logger.debug("Stop Automating Browser: " + reqid)
        browser = self.browsers.pop(reqid, None)
        if browser is None:
            return
        await self.gracefully_shutdown_browser(browser)

    async def init(self) -> None:
        logger.info("MultiBrowserDriver[init]: initializing")
        await super().init()
        self.pubsub_channel = await self.get_auto_event_channel()
        self.pubsub_task = self.loop.create_task(self.pubsub_loop())

    async def shutdown(self) -> int:
        logger.info("MultiBrowserDriver[shutdown]: shutting down")
        for browser in self.browsers.values():
            await self.gracefully_shutdown_browser(browser)
        self.browsers.clear()
        await self.clean_up()
        logger.info("MultiBrowserDriver[shutdown]: exiting")
        return self.determine_exit_code()

    def on_browser_exit(self, info: BrowserExitInfo) -> None:
        sig = f"MultiBrowserDriver[on_browser_exit(info={info})]"
        logging.info(f"{sig}: the browser exited")
        browser = self.browsers.pop(info.auto_info.reqid, None)
        if browser is None:
            return
        browser.remove_all_listeners()
        self._browser_exit_infos.append(info)
        if len(self.browsers) == 0:
            logging.info(f"{sig}: no more active browsers, shutting down")
            self.shutdown_condition.initiate_shutdown()
