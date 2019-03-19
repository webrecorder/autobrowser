from abc import ABC
from asyncio import AbstractEventLoop, CancelledError, Task, sleep as aio_sleep
from typing import Any, Dict, List, Optional, Union
from ujson import loads as ujson_loads

from aioredis import Channel

from autobrowser.automation import AutomationConfig, BrowserExitInfo
from autobrowser.chrome_browser import Chrome
from autobrowser.errors import BrowserStagingError
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
        self.browser_info_url: str = self.conf.make_shepherd_url(GET_BROWSER_INFO_URL)
        self.request_new_browser_url: str = self.conf.make_shepherd_url(REQ_BROWSER_URL)
        self.init_browser_url: str = self.conf.make_shepherd_url(INIT_BROWSER_URL)
        self.pubsub_channel: Channel = None
        self.pubsub_task: Task = None

    async def stage_new_browser(
        self, browser_id: str, data: Optional[Any] = None
    ) -> str:
        async with self.session.post(
            self.conf.request_new_browser_url(browser_id), data=data
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
        headers = dict(Host="localhost")
        eloop = self.loop
        logged_method = f"init_new_browser<browser_id={browser_id}, data={data}>"

        self_session_get = self.session.get
        self_logger_info = self.logger.info
        self_logger_exception = self.logger.exception
        init_browser_url = self.conf.init_browser_url(reqid)

        while 1:
            async with self_session_get(init_browser_url, headers=headers) as response:
                try:
                    data = await response.json()
                except Exception as e:
                    self_logger_exception(
                        logged_method, "Browser Init Failed", exc_info=e
                    )
                    return None
                if "cmd_port" in data:
                    break
                self_logger_info(logged_method, f"Waiting for Browser: {data}")
                await aio_sleep(WAIT_TIME, loop=eloop)
        tab_datas = await self.wait_for_tabs(data.get("ip"), self.conf.num_tabs)
        return dict(ip=data.get("ip"), reqid=reqid, tab_datas=tab_datas)

    async def wait_for_tabs(self, ip: str, num_tabs: int = 0) -> List[Dict[str, str]]:
        self_find_browser_tabs = self.find_browser_tabs
        self_logger_info = self.logger.info

        eloop = self.loop
        log_method = f"wait_for_tabs(ip={ip}, num_tabs={num_tabs})"

        while 1:
            tab_datas = await self_find_browser_tabs(ip=ip)
            if tab_datas:
                break
            self_logger_info(log_method, "Waiting for first tab")
            await aio_sleep(WAIT_TIME, loop=eloop)

        if num_tabs > 0:
            self_create_browser_tab = self.create_browser_tab
            tab_datas_append = tab_datas.append
            for _ in range(num_tabs - 1):
                tab_data = await self_create_browser_tab(ip)
                tab_datas_append(tab_data)

        return tab_datas

    async def find_browser_tabs(
        self,
        ip: Optional[str] = None,
        url: Optional[str] = None,
        require_ws: Optional[bool] = True,
    ) -> List[Dict[str, str]]:
        filtered_tabs: List[Dict[str, str]] = []
        logged_method = f"find_browser_tabs<ip={ip}, url={url}>"

        try:
            async with self.session.get(self.conf.cdp_json_url(ip)) as res:
                tabs = await res.json(loads=ujson_loads)
        except Exception as e:
            self.logger.exception(
                logged_method,
                "An exception was raised while making the CDP_JSON request",
                exc_info=e,
            )
            return filtered_tabs

        self_logger_info = self.logger.info
        filtered_tabs_append = filtered_tabs.append

        for tab in tabs:
            self_logger_info(logged_method, f"Tab = {tab}")

            if require_ws and "webSocketDebuggerUrl" not in tab:
                continue

            if tab.get("type") == "page" and (not url or url == tab["url"]):
                filtered_tabs_append(tab)

        return filtered_tabs

    async def get_ip_for_reqid(self, reqid: str) -> Optional[str]:
        """Retrieve the ip address associated with a requests id

        :param reqid: The request id to retrieve the ip address for
        :return: The ip address associated with the request id if it exists
        """
        url = self.conf.browser_info_url(reqid)
        logged_method = f"get_ip_for_reqid(reqid={reqid})"
        self.logger.info(
            logged_method, f"Retrieving the ip associated with the reqid <url={url}>"
        )
        try:
            async with self.session.get(url) as res:
                json = await res.json(loads=ujson_loads)  # type: Dict[str, str]
                return json.get("ip")
        except Exception as e:
            self.logger.exception(logged_method, "", exc_info=e)
        return None

    async def create_browser_tab(self, ip: str) -> Dict[str, str]:
        async with self.session.get(self.conf.cdp_json_new_url(ip)) as res:
            return await res.json(loads=ujson_loads)

    async def clean_up(self) -> None:
        self.logger.info("clean_up", "closing redis connection")
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
        self.logger.info("init", "initializing")
        await super().init()
        tab_datas = await self.wait_for_tabs(
            self.conf.browser_host_ip, self.conf.num_tabs
        )
        self.browser = Chrome(
            config=self.conf,
            behavior_manager=self.behavior_manager,
            session=self.session,
            redis=self.redis,
            loop=self.loop,
        )
        self.browser.on(Chrome.Events.Exiting, self.on_browser_exit)
        await self.browser.init(tab_datas)
        self.pubsub_task = self.loop.create_task(self.pubsub_loop())

    async def get_auto_event_channel(self) -> Channel:
        channels = await self.redis.subscribe(
            "wr.auto-event:{reqid}".format(reqid=self.conf.reqid)
        )
        return channels[0]

    async def pubsub_loop(self) -> None:
        logged_method = "pubsub_loop"
        self.pubsub_channel = await self.get_auto_event_channel()
        self.logger.debug(logged_method, "started")

        while await self.pubsub_channel.wait_message():
            msg = await self.pubsub_channel.get(encoding="utf-8", decoder=ujson_loads)
            self.logger.debug(logged_method, f"got message {msg}")

            if msg["cmd"] == "stop":
                for tab in self.browser.tabs.values():
                    await tab.pause_behaviors()

            elif msg["cmd"] == "start":
                for tab in self.browser.tabs.values():
                    await tab.resume_behaviors()

            elif msg["cmd"] == "shutdown":
                self.shutdown_condition.initiate_shutdown()
            self.logger.debug(logged_method, "waiting for another message")
        self.logger.debug(logged_method, "stopped")

    async def shutdown(self) -> int:
        self.logger.info("shutdown", "shutting down")
        if self.browser is not None:
            await self.gracefully_shutdown_browser(self.browser)
            self.browser = None
        await super().clean_up()
        self.logger.info("shutdown", "exiting")
        return self.determine_exit_code()

    def on_browser_exit(self, info: BrowserExitInfo) -> None:
        self.logger.info(f"on_browser_exit(info={info})", "The browser exited")
        self._browser_exit_infos.append(info)
        self.browser.remove_all_listeners()
        self.browser = None
        self.shutdown_condition.initiate_shutdown()

    def __str__(self) -> str:
        return f"SingleBrowserDriver(browser={self.browser}, conf={self.conf})"


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
        logged_method = "pubsub_loop"
        while await self.pubsub_channel.wait_message():
            msg = await self.pubsub_channel.get(encoding="utf-8", decoder=ujson_loads)
            self.logger.debug(logged_method, f"got message {msg}")
            if msg["cmd"] == "start":
                await self.add_browser(msg["reqid"])
            elif msg["cmd"] == "stop":
                await self.remove_browser(msg["reqid"])

    async def add_browser(self, reqid: str) -> None:
        self.logger.debug(f"add_browser(reqid={reqid})", "Start Automating Browser")
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
                    self.conf.browser_id, self.conf.get("cdata")
                )
                tab_datas = results["tab_datas"]

            browser = Chrome(
                config=self.conf,
                behavior_manager=self.behavior_manager,
                session=self.session,
                redis=self.redis,
                loop=self.loop,
            )

            await browser.init(tab_datas)
            self.browsers[reqid] = browser
            browser.on(Chrome.Events.Exiting, self.on_browser_exit)

    async def remove_browser(self, reqid: str) -> None:
        self.logger.debug(f"remove_browser(reqid={reqid})", "Stop Automating Browser")
        browser = self.browsers.pop(reqid, None)
        if browser is None:
            return
        await self.gracefully_shutdown_browser(browser)

    async def init(self) -> None:
        self.logger.info("init", "initializing")
        await super().init()
        self.pubsub_channel = await self.get_auto_event_channel()
        self.pubsub_task = self.loop.create_task(self.pubsub_loop())

    async def shutdown(self) -> int:
        logged_method = "shutdown"
        self.logger.info(logged_method, "shutting down")
        for browser in self.browsers.values():
            await self.gracefully_shutdown_browser(browser)
        self.browsers.clear()
        await self.clean_up()
        self.logger.info(logged_method, "exiting")
        return self.determine_exit_code()

    def on_browser_exit(self, info: BrowserExitInfo) -> None:
        logged_method = f"on_browser_exit(info={info})"
        self.logger.info(logged_method, "the browser exited")
        browser = self.browsers.pop(info.auto_info.reqid, None)
        if browser is None:
            return
        browser.remove_all_listeners()
        self._browser_exit_infos.append(info)
        if len(self.browsers) == 0:
            self.logger.info(logged_method, "no more active browsers, shutting down")
            self.shutdown_condition.initiate_shutdown()

    def __str__(self) -> str:
        return f"SingleBrowserDriver(browsers={self.browsers}, conf={self.conf})"
