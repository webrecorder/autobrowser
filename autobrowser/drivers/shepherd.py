from abc import ABC
from asyncio import AbstractEventLoop, CancelledError, Task, sleep
from typing import Any, Dict, List, Optional, Union

from ujson import loads
from aioredis import Channel

from autobrowser.automation import AutomationConfig, BrowserExitInfo
from autobrowser.chrome_browser import Chrome
from autobrowser.errors import BrowserStagingError
from autobrowser.events import Events
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
        """Stages a new browser from shepherd returning an request id
        to be used when communicating with shepherd about the newly staged browser

        :param browser_id: The id of the browser to be staged
        :param data: Optional data to be sent with the stage request
        :return: The request id for the newly staged browser
        """
        async with self.session.post(
            self.conf.request_new_browser_url(browser_id), data=data
        ) as response:
            json = await response.json(loads=loads)  # type: Dict[str, str]
        reqid = json.get("reqid")
        if reqid is None:
            raise BrowserStagingError(f"Could not stage browser with id = {browser_id}")
        return reqid

    async def init_new_browser(
        self, browser_id: str, data: Optional[Any] = None
    ) -> Optional[Dict[str, Union[str, List[Dict[str, str]]]]]:
        """Initializes the a new browser identified by the supplied browser id

        :param browser_id: The id of the new browser
        :param data: Optional data to be sent with the initialization request
        :return: An dictionary containing the information about the newly initialized browser
        """
        reqid = await self.stage_new_browser(browser_id, data)
        headers = {"Host": "localhost"}
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
                await sleep(WAIT_TIME, loop=eloop)
        tab_datas = await self.wait_for_tabs(data.get("ip"), self.conf.num_tabs)
        return {"ip": data.get("ip"), "reqid": reqid, "tab_datas": tab_datas}

    async def wait_for_tabs(self, ip: str, num_tabs: int = 0) -> List[Dict[str, str]]:
        """Waits for tabs in a remote browser, signified by the supplied ip address, to become available.
        If the `num_tabs` keyword argument is supplied with a number greater than zero, that
        many additional tabs will be created in the remote browser

        :param ip: The ip address of the remote browser
        :param num_tabs: How many additional tabs are to be created in the remote browser
        :return: A list of dictionaries containing information about the remote browser tabs
        """
        find_browser_tabs = self.find_browser_tabs
        log = self.logger.info

        eloop = self.loop
        log_method = f"wait_for_tabs(ip={ip}, num_tabs={num_tabs})"

        while 1:
            tab_datas = await find_browser_tabs(ip=ip)
            if tab_datas:
                break
            log(log_method, "Waiting for first tab")
            await sleep(WAIT_TIME, loop=eloop)

        if num_tabs > 0:
            create_browser_tab = self.create_browser_tab
            tab_datas_append = tab_datas.append
            for _ in range(num_tabs - 1):
                tab_data = await create_browser_tab(ip)
                tab_datas_append(tab_data)

        return tab_datas

    async def find_browser_tabs(
        self,
        ip: Optional[str] = None,
        url: Optional[str] = None,
        require_ws: Optional[bool] = True,
    ) -> List[Dict[str, str]]:
        """Retrieves a list of tabs from a remote browser, signified by the supplied ip address,
        filtering the retrieved list of tabs by requiring a tab to have a ws url and or its page URL
        is not equal to the supplied url.

        :param ip: The ip address of the remote browser
        :param url: Optional URL used to exclude tab(s)
        :param require_ws: Should the list of tabs returned only include tabs with a ws url. Defaults to true
        :return: A list of dictionaries containing information about tabs in the remote browser
        """
        filtered_tabs: List[Dict[str, str]] = []
        logged_method = f"find_browser_tabs<ip={ip}, url={url}>"

        try:
            async with self.session.get(self.conf.cdp_json_url(ip)) as res:
                tabs = await res.json(loads=loads)
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
                json = await res.json(loads=loads)  # type: Dict[str, str]
                return json.get("ip")
        except Exception as e:
            self.logger.exception(logged_method, "", exc_info=e)
        return None

    async def create_browser_tab(self, ip: str) -> Dict[str, str]:
        """Creates a new browser tab in a remote browser signified by the supplied ip address.

        :param ip: The ip of the remote browser
        :return: A dictionary containing information about the newly created tab
        """
        async with self.session.get(self.conf.cdp_json_new_url(ip)) as res:
            return await res.json(loads=loads)

    async def clean_up(self) -> None:
        """Closes the pubsub channel and calls the clean_up method the super class"""
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
        self.browser.on(Events.BrowserExiting, self.on_browser_exit)
        await self.browser.init(tab_datas)
        self.pubsub_channel = await self.get_auto_event_channel()
        self.pubsub_task = self.loop.create_task(self.pubsub_loop())

    async def get_auto_event_channel(self) -> Channel:
        """Returns a pubsub channel for the automation `wr.auto-event:{requid}`

        :return: The automation's pubsub channel
        """
        channels = await self.redis.subscribe(
            "wr.auto-event:{reqid}".format(reqid=self.conf.reqid)
        )
        return channels[0]

    async def pubsub_loop(self) -> None:
        """Waits for messages delivered via the automation's pubsub channel and
        handles them accordingly.

        Messages:
          - start: all tabs start running behaviors
          - stop: all tabs if they have an running behavior are paused
          - shutdown: stops the running automation
        """
        logged_method = "pubsub_loop"
        self.logger.debug(logged_method, "started")

        while 1:
            have_message = await self.pubsub_channel.wait_message()
            if not have_message:
                break
            msg = await self.pubsub_channel.get(encoding="utf-8", decoder=loads)
            self.logger.debug(logged_method, f"got message {msg}")

            if msg["cmd"] == "stop":
                await self._pause_behaviors()

            elif msg["cmd"] == "start":
                await self._resume_running_behaviors()

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

    async def _pause_behaviors(self) -> None:
        """Calls the pause_behaviors method of all tabs the browser is managing"""
        for tab in self.browser.tabs.values():
            await tab.pause_behaviors()

    async def _resume_running_behaviors(self) -> None:
        """Calls the resume_behaviors method of all tabs the browser is managing"""
        for tab in self.browser.tabs.values():
            await tab.resume_behaviors()

    def __str__(self) -> str:
        return f"SingleBrowserDriver(browser={self.browser}, conf={self.conf})"


class MultiBrowserDriver(ShepherdDriver):
    """A driver for running multiple automations via multiple remote browser"""

    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.browsers: Dict[str, Chrome] = {}

    async def get_auto_event_channel(self) -> Channel:
        """Returns a pubsub channel for the automation `wr.auto-event:{requid}`

        :return: The automation's pubsub channel
        """
        channels = await self.redis.subscribe(
            "wr.auto-event:{reqid}".format(reqid=self.conf.reqid)
        )
        return channels[0]

    async def pubsub_loop(self) -> None:
        """Waits for messages delivered via the automation's pubsub channel and
        handles them accordingly.

        Messages:
          - start: adds a the browser signified by the message's requid to the managed browsers
          - stop: removes a the browser signified by the message's requid to the managed browsers
        """
        logged_method = "pubsub_loop"

        while 1:
            have_message = await self.pubsub_channel.wait_message()
            if not have_message:
                break
            msg = await self.pubsub_channel.get(encoding="utf-8", decoder=loads)
            self.logger.debug(logged_method, f"got message {msg}")
            if msg["cmd"] == "start":
                await self.add_browser(msg["reqid"])
            elif msg["cmd"] == "stop":
                await self.remove_browser(msg["reqid"])
            self.logger.debug(logged_method, "waiting for another message")

        self.logger.debug(logged_method, "stopped")

    async def add_browser(self, reqid: str) -> None:
        """Adds a browser, signified by the supplied request id, to the managed browser dictionary

        :param reqid: The request id of the browser to be added
        """
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
            browser.on(Events.BrowserExiting, self.on_browser_exit)

    async def remove_browser(self, reqid: str) -> None:
        """Removes a browser, signified by the supplied request id, from the managed browser dictionary

        :param reqid: The request id of the browser to be removed
        """
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
