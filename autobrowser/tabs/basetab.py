"""Abstract base classes that implements the base functionality of a tab as defined by autobrowser.abcs.Tab"""
from asyncio import AbstractEventLoop, CancelledError, Task, gather, sleep
from base64 import b64decode
from io import BytesIO
from typing import Any, Dict, Optional

from aiohttp import ClientResponseError, ClientSession
from aioredis import Redis
from cripy import Client, connect
from math import ceil
from simplechrome import NetworkIdleMonitor

from autobrowser.abcs import Behavior, BehaviorManager, Browser, Tab
from autobrowser.automation import AutomationConfig, CloseReason, TabClosedInfo
from autobrowser.events import Events
from autobrowser.util import AutoLogger, Helper, create_autologger

__all__ = ["BaseTab"]


class BaseTab(Tab):
    """An abstract automation tab class that represents a browser tab in a running browser and
    provides the base implementation for
    """

    __slots__ = [
        "_behavior_run_task",
        "_behaviors_paused",
        "_close_reason",
        "_connection_closed",
        "_default_handling_of_dialogs",
        "_graceful_shutdown",
        "_id",
        "_reconnect_promise",
        "_reconnecting",
        "_running",
        "_running_behavior",
        "_url",
        "_viewport",
        "browser",
        "client",
        "logger",
        "redis",
        "session",
        "tab_data",
    ]

    def __init__(
        self,
        browser: Browser,
        tab_data: Dict[str, str],
        redis: Optional[Redis] = None,
        session: Optional[ClientSession] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(loop=Helper.ensure_loop(browser.loop))
        self.browser: Browser = browser
        self.redis = redis
        self.session = session
        self.tab_data: Dict[str, str] = tab_data
        self.client: Optional[Client] = None
        self.logger: AutoLogger = create_autologger("tabs", self.__class__.__name__)
        self._url: str = self.tab_data["url"]
        self._id: str = self.tab_data["id"]
        self._behaviors_paused: bool = False
        self._connection_closed: bool = False
        self._running: bool = False
        self._reconnecting: bool = False
        self._graceful_shutdown: bool = False
        self._default_handling_of_dialogs: bool = True
        self._behavior_run_task: Optional[Task] = None
        self._reconnect_promise: Optional[Task] = None
        self._running_behavior: Optional[Behavior] = None
        self._close_reason: Optional[CloseReason] = None
        self._viewport: Optional[Dict] = None

    @property
    def loop(self) -> AbstractEventLoop:
        return self._loop

    @property
    def behaviors_paused(self) -> bool:
        """Are the behaviors paused"""
        return self._behaviors_paused

    @property
    def connection_closed(self) -> bool:
        return self._connection_closed

    @property
    def behavior_manager(self) -> BehaviorManager:
        return self.browser.behavior_manager

    @property
    def config(self) -> AutomationConfig:
        return self.browser.config

    @property
    def autoid(self) -> str:
        return self.browser.autoid

    @property
    def reqid(self) -> str:
        return self.browser.reqid

    @property
    def tab_id(self) -> str:
        """Returns the id of the tab this class is controlling"""
        return self._id

    @property
    def tab_url(self) -> str:
        """Returns the URL of the tab this class is controlling"""
        return self._url

    @property
    def running(self) -> bool:
        """Is this tab running (active client connection)"""
        return self._running

    @property
    def reconnecting(self) -> bool:
        """Is this tab attempting to reconnect to the tab"""
        return self._running and self._reconnecting

    def devtools_reconnect(self, result: Dict[str, str]) -> None:
        """Callback used to reconnect to the browser tab when the client connection was
        replaced with the devtools."""
        if result["reason"] == "replaced_with_devtools":
            self._reconnecting = True
            self._running = False
            self._reconnect_promise = self._loop.create_task(self._wait_for_reconnect())

    def set_running_behavior(self, behavior: Behavior) -> None:
        """Set the tabs running behavior (done automatically by
        behaviors)

        :param behavior: The behavior that is currently running
        """
        self._running_behavior = behavior

    def unset_running_behavior(self, behavior: Behavior) -> None:
        """Un-sets the tabs running behavior (done automatically by
        behaviors)

        :param behavior: The behavior that was running
        """
        if self._running_behavior and behavior is self._running_behavior:
            self._running_behavior = None

    async def pause_behaviors(self) -> None:
        """Sets the behaviors paused flag to true"""
        await self.evaluate_in_page("window.$WBBehaviorPaused = true;")
        self._behaviors_paused = True

    async def resume_behaviors(self) -> None:
        """Sets the behaviors paused flag to false"""
        await self.evaluate_in_page("window.$WBBehaviorPaused = false;")
        self._behaviors_paused = False

    async def stop_reconnecting(self) -> None:
        """Stops the reconnection process if it is under way"""
        if not self.reconnecting or self._reconnect_promise is None:
            return
        if self._reconnect_promise.done():
            return

        try:
            self._reconnect_promise.cancel()
            await self._reconnect_promise
        except Exception:
            pass
        self._reconnecting = False

    async def wait_for_reconnect(self) -> None:
        """If the client connection has been disconnected and we are
        reconnecting, waits for reconnection to happen"""
        if not self.reconnecting or self._reconnect_promise is None:
            return
        if self._reconnect_promise.done():
            return
        await self._reconnect_promise

    async def wait_for_net_idle(
        self, num_inflight: int = 2, idle_time: int = 2, global_wait: int = 60
    ) -> None:
        """Returns a future that  resolves once network idle occurs.

        See the options of autobrowser.util.netidle.monitor for a complete
        description of the available arguments
        """
        logged_method = "wait_for_net_idle"
        self.logger.debug(logged_method, "waiting for network idle")
        await NetworkIdleMonitor.monitor(
            self.client,
            num_inflight=num_inflight,
            idle_time=idle_time,
            global_wait=global_wait,
            loop=self.loop,
        )
        self.logger.debug(logged_method, "network idle reached")

    async def evaluate_in_page(
        self, js_string: str, contextId: Optional[Any] = None
    ) -> Any:
        """Evaluates the supplied string of JavaScript in the tab

        :param js_string: The string of JavaScript to be evaluated
        :return: The results of the evaluation if any
        """
        logged_method = "evaluate_in_page"
        self.logger.debug(logged_method, "evaluating js in page")
        try:
            results = await self.client.Runtime.evaluate(
                js_string,
                contextId=contextId,
                userGesture=True,
                awaitPromise=True,
                includeCommandLineAPI=True,
                returnByValue=True,
            )
        except Exception as e:
            if not isinstance(e, CancelledError):
                self.logger.exception(
                    logged_method,
                    "evaluating js in page failed due to an python error",
                    exc_info=e,
                )
            return {"done": True}
        js_exception = results.get("exceptionDetails")
        if js_exception:
            jse_dets = Helper.getExceptionMessage(js_exception)
            self.logger.critical(
                logged_method,
                f"evaluating js in page failed due to an JS error - {jse_dets}",
            )
            return {}
        return results.get("result", {}).get("value")

    async def goto(self, url: str, *args: Any, **kwargs: Any) -> Any:
        """Initiates browser navigation to the supplied url.

        See cripy.protocol.Page for more information about additional
        arguments or https://chromedevtools.github.io/devtools-protocol/tot/Page#method-navigate

        :param url: The URL to be navigated to
        :param kwargs: Additional arguments to Page.navigate
        :return: The information returned by Page.navigate
        """
        self.logger.info(f"goto(url={url})", f"navigating to the supplied URL")
        return await self.client.Page.navigate(url, **kwargs)

    async def connect_to_tab(self) -> None:
        """Initializes the connection to the remote browser tab and
        sets up listeners for when the connection is closed/detached or the
        browser tab crashes
        """
        if self._running:
            return
        logged_method = "connect_to_tab"
        self.logger.debug(logged_method, f"connecting to the browser {self.tab_data}")
        self.client = await connect(
            self.tab_data["webSocketDebuggerUrl"], loop=self.loop
        )

        self.logger.debug(logged_method, "connected to browser")

        self.client.on(Client.Events.Disconnected, self._on_connection_closed)
        self.client.Inspector.detached(self.devtools_reconnect)
        self.client.Inspector.targetCrashed(self._on_inspector_crashed)

        await gather(
            self.client.Page.enable(),
            self.client.Network.enable(),
            self.client.Runtime.enable(),
            loop=self.loop,
        )
        self.logger.info(logged_method, "enabled domains")
        if self._default_handling_of_dialogs:
            self.client.Page.javascriptDialogOpening(self.__handle_page_dialog)

    async def init(self) -> None:
        """Initialize the client connection to the tab.

        Subclasses are expected to call this method from their
        implementation. This can be the only call in their
        implementation.
        """
        self.logger.debug("init", f"running = {self.running}")
        if self._running:
            return
        await self.connect_to_tab()
        await self._apply_browser_overrides()
        self._running = True

    async def close(self) -> None:
        """Close the client connection to the tab.

        Subclasses are expected to call this method from their
        implementation. This can be the only call in their
        implementation.
        """
        self._running = False
        if self._close_reason is None:
            if self._graceful_shutdown:
                self._close_reason = CloseReason.GRACEFULLY
            else:
                self._close_reason = CloseReason.CLOSED
        self.logger.info("close", "closing client")
        if self.reconnecting:
            await self.stop_reconnecting()
        if self.client:
            self.client.remove_all_listeners()
            await self.client.dispose()
            self.client = None
        self.emit(Events.TabClosed, TabClosedInfo(self.tab_id, self._close_reason))

    async def shutdown_gracefully(self) -> None:
        """Initiates the graceful shutdown of the tab"""
        logged_method = "shutdown_gracefully"
        self.logger.info(logged_method, "shutting down")
        self._graceful_shutdown = True
        await self.close()
        self.logger.info(logged_method, "shutdown complete")

    async def post_behavior_run(self) -> None:
        await self.capture_and_upload_screenshot()
        await self.extract_page_data_and_send()

    async def capture_screenshot(self) -> bytes:
        """Capture a screenshot (in png format) of the current page.

        :return: The captured screenshot as bytes
        """
        logged_method = "capture_screenshot"
        self.logger.info(logged_method, "capturing screenshot of page")
        # focus our tabs main window just in case we lost focus somewhere
        # i suspect that chrome has issues with non-focused/activated windows
        # and screenshots
        await self.client.send(
            "Target.activateTarget", {"targetId": self.tab_data["id"]}
        )
        # get page metrics so we can resize, virtually, to the full page contents
        metrics = await self.client.Page.getLayoutMetrics()
        content_size = metrics["contentSize"]
        content_width = ceil(content_size["width"])
        content_height = ceil(content_size["height"])

        if self.config.screenshot_dimensions is not None:
            # use configured screen shot width height
            sc_width, sc_height = self.config.screenshot_dimensions
        else:
            # use content width height
            sc_width = content_width
            sc_height = content_height

        # do the virtual resize, take the screenshot, and  then reset
        await self.client.Emulation.setDeviceMetricsOverride(
            width=content_width,
            height=content_height,
            mobile=self._viewport["mobile"],
            deviceScaleFactor=self._viewport["deviceScaleFactor"],
            screenOrientation=self._viewport["screenOrientation"],
        )
        # NOTE: we may need fromSurface=False to make our screen shot consider the viewport only
        # not the surface (the entirety of the rendered chrome)
        result = await self.client.Page.captureScreenshot(
            clip={"x": 0, "y": 0, "width": sc_width, "height": sc_height, "scale": 1},
            format="png",
        )
        # reset back to our configured viewport
        await self.client.Emulation.setDeviceMetricsOverride(**self._viewport)
        self.logger.info(logged_method, "captured screenshot of page")
        return b64decode(result.get("data", b""))

    async def capture_and_upload_screenshot(self) -> None:
        if not self.config.should_take_screenshot:
            return
        logged_method = "capture_and_upload_screenshot"
        screen_shot = None
        try:
            screen_shot = await self.capture_screenshot()
        except Exception as e:
            self.logger.exception(
                logged_method, "capturing a screenshot of the page failed", exc_info=e
            )
        if screen_shot is not None:
            self.logger.info(
                logged_method,
                "sending the captured screenshot to the configured endpoint",
            )
            config = self.config
            content_type = "image/png"
            await self._upload_data(
                config.screenshot_api_url,
                params={
                    "reqid": config.reqid,
                    "target_uri": config.screenshot_target_uri.format(url=self._url),
                    "content_type": content_type,
                },
                data=BytesIO(screen_shot),
                headers={"content-type": content_type},
            )

    async def extract_page_data_and_send(self) -> None:
        config = self.config
        if self.config.should_retrieve_raw_dom:
            try:
                dom = await self.client.DOM.getDocument(depth=-1, pierce=True)
            except Exception as e:
                dom = None
            if dom is not None:
                await self._upload_data(
                    config.extracted_raw_dom_api_url,
                    params={"reqid": config.reqid},
                    json=dom,
                )

        if self.config.should_retrieve_mhtml:
            try:
                mhtml = await self.client.Page.captureSnapshot("mthml")
            except Exception as e:
                mhtml = None
            if mhtml is not None:
                content_type = "text/mhtml"
                await self._upload_data(
                    config.extracted_mhtml_api_url,
                    params={"reqid": config.reqid},
                    data=mhtml,
                    headers={"content-type": content_type},
                )

    async def navigation_reset(self) -> None:
        logged_method = "navigation_reset"
        self.logger.debug(logged_method, "Resetting tab to about:blank")
        try:
            await self.goto("about:blank")
        except Exception as e:
            self.logger.exception(
                logged_method, "Resetting to about:blank failed at end", exc_info=e
            )
        else:
            self.logger.debug(logged_method, "Tab reset to about:blank")

    async def _apply_browser_overrides(self) -> None:
        """Applies any configured browser overrides.
        If none were configured, ensures that the User-Agent
        of the browser does not blatantly state we are headless

        Available overrides:
          - User-Agent
          - Accept-Language HTTP header
          - The navigator.platform value
          - Extra HTTP headers to be sent by the browser
            Accept-Language and User-Agent is not included here
          - Cookies to be pre-loaded
          - Device emulation
          - Geo location emulation
        """
        config = self.config
        ua = config.browser_override("user_agent")
        if ua is None:
            version_info = await self.client.Browser.getVersion()
            ua = version_info["userAgent"].replace("Headless", "")

        geo_location = config.browser_override("geo_location")
        if geo_location is not None:
            await self.client.Emulation.setGeolocationOverride(
                latitude=geo_location["latitude"], longitude=geo_location["longitude"]
            )
        accept_lang = config.browser_override("accept_language")
        nav_plat = config.browser_override("navigator_platform")
        await self.client.Network.setUserAgentOverride(
            ua, acceptLanguage=accept_lang, platform=nav_plat
        )
        cookies = config.browser_override("cookies")
        if cookies is not None:
            await self.client.Network.setCookies(cookies)

        headers = config.browser_override("extra_headers")
        if headers is not None:
            await self.client.Network.setExtraHTTPHeaders(headers)

        device = config.browser_override("device")
        screen_orientation = {"angle": 0, "type": "portraitPrimary"}
        if device is not None:
            vp = device["viewport"]  # type: Dict
            if vp.pop("isLandscape", False):
                screen_orientation["angle"] = 90
                screen_orientation["type"] = "landscapePrimary"

            await self.client.send(
                "Emulation.setTouchEmulationEnabled",
                {
                    "enabled": vp.pop("hasTouch", False),
                    "maxTouchPoints": vp.pop("maxTouchPoints", 1),
                },
            )
            self._viewport = {
                "mobile": vp.pop("isMobile", False),
                "width": vp["width"],
                "height": vp["height"],
                "deviceScaleFactor": vp.pop("deviceScaleFactor", 1),
                "screenOrientation": screen_orientation,
            }
            await self.client.Emulation.setDeviceMetricsOverride(**self._viewport)
            return

        metrics = await self.client.Page.getLayoutMetrics()
        vv = metrics["visualViewport"]
        self._viewport = {
            "mobile": False,
            "width": vv["clientWidth"],
            "height": vv["clientHeight"],
            "deviceScaleFactor": 1,
            "screenOrientation": screen_orientation,
        }

    async def _upload_data(
        self,
        url: str,
        params: Optional[Dict] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[Dict] = None,
    ) -> None:
        """Uploads the supplied data or json to the supplied URL.
        Method used is PUT

        :param url: The URL of the upload endpoint
        :param params: Query Params for the Request
        :param data: Optional non JSON data
        :param json: Optional data
        :param headers: Optional HTTP headers to be used
        """
        logged_method = "_upload_data"
        try:
            async with self.session.put(
                url, params=params, data=data, json=json, headers=headers
            ) as resp:
                resp.raise_for_status()
        except ClientResponseError as e:
            self.logger.exception(
                logged_method,
                "sent the data but the server indicates a failure",
                exc_info=e,
            )
        except Exception as e:
            self.logger.exception(logged_method, "sending the data failed", exc_info=e)
        else:
            self.logger.info(logged_method, "sent the data to the configured endpoint")

    async def _wait_for_reconnect(self) -> None:
        """Attempt to reconnect to browser tab after client connection was replayed with
        the devtools"""
        self_init = self.init
        loop = self.loop
        while True:
            try:
                await self_init()
                break
            except Exception as e:
                print(e)

            await sleep(3.0, loop=loop)
        self._reconnecting = False
        if self._reconnect_promise and not self._reconnect_promise.done():
            self._reconnect_promise.cancel()

    async def _on_inspector_crashed(self, *args: Any, **kwargs: Any) -> None:
        """Listener function for when the target has crashed.

        If the tab is running the close reason will be set to TARGET_CRASHED and
        the tab will be closed
        """
        if self._running:
            self.logger.critical(
                "_on_inspector_crashed", f"target crashed while running - {self._url}"
            )
            self._close_reason = CloseReason.TARGET_CRASHED
            await self.close()

    async def _on_connection_closed(self, *args: Any, **kwargs: Any) -> None:
        """Listener function for when the connection has clossed.

        If the tab is running the close reason will be set to CONNECTION_CLOSED and
        the tab will be closed
        """
        if self._running:
            self._connection_closed = True
            self.logger.critical(
                "_on_connection_closed",
                f"connection closed while running - {self._url}",
            )
            self._close_reason = CloseReason.CONNECTION_CLOSED
            await self.close()

    async def __handle_page_dialog(self, event: Dict) -> None:
        _type = event.get("type")
        if _type == "alert":
            accept = True
        else:
            accept = False
        await self.client.Page.handleJavaScriptDialog(accept=accept)

    def __str__(self) -> str:
        name = self.__class__.__name__
        info = f"graceful_shutdown={self._graceful_shutdown}, tab_id={self.tab_id}"
        return f"{name}(url={self._url}, running={self._running} connected={not self._connection_closed}, {info})"

    def __repr__(self) -> str:
        return self.__str__()
