"""Abstract base classes that implements the base functionality of a tab as defined by autobrowser.abcs.Tab"""
from abc import ABC
from asyncio import AbstractEventLoop, Task, gather as aio_gather, sleep as aio_sleep
from base64 import b64decode
from io import BytesIO
from math import ceil as math_ceil
from typing import Any, Awaitable, Dict, Optional

from aiohttp import ClientResponseError, ClientSession
from aioredis import Redis
from cripy import Client, connect
from simplechrome.network_idle_monitor import NetworkIdleMonitor

from autobrowser.abcs import Behavior, BehaviorManager, Browser, Tab
from autobrowser.automation import AutomationConfig, CloseReason, TabClosedInfo
from autobrowser.util import AutoLogger, Helper, create_autologger

__all__ = ["BaseTab"]


class BaseTab(Tab, ABC):
    """Base Automation Tab Class that represents a browser tab in a running browser"""

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
        self.client: Client = None
        self.target_info: Optional[Dict] = None
        self.logger: AutoLogger = create_autologger("tabs", self.__class__.__name__)
        self._url: str = self.tab_data["url"]
        self._id: str = self.tab_data["id"]
        self._curr_behavior_url: str = ""
        self._behaviors_paused: bool = False
        self._connection_closed: bool = False
        self._running: bool = False
        self._reconnecting: bool = False
        self._graceful_shutdown: bool = False
        self._behavior_run_task: Optional[Task] = None
        self._reconnect_promise: Optional[Task] = None
        self._running_behavior: Optional[Behavior] = None
        self._close_reason: Optional[CloseReason] = None

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

    def devtools_reconnect(self, result: Dict[str, str]) -> None:
        """Callback used to reconnect to the browser tab when the client connection was
        replaced with the devtools."""
        if result["reason"] == "replaced_with_devtools":
            self._reconnecting = True
            self._running = False
            self._reconnect_promise = self._loop.create_task(self._wait_for_reconnect())

    async def wait_for_reconnect(self) -> None:
        """If the client connection has been disconnected and we are
        reconnecting, waits for reconnection to happen"""
        if not self.reconnecting or self._reconnect_promise is None:
            return
        if self._reconnect_promise.done():
            return
        await self._reconnect_promise

    def wait_for_net_idle(
        self, num_inflight: int = 2, idle_time: int = 2, global_wait: int = 60
    ) -> Awaitable[None]:
        """Returns a future that  resolves once network idle occurs.

        See the options of autobrowser.util.netidle.monitor for a complete
        description of the available arguments
        """
        return NetworkIdleMonitor.monitor(
            self.client,
            num_inflight=num_inflight,
            idle_time=idle_time,
            global_wait=global_wait,
            loop=self.loop,
        )

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

            await aio_sleep(3.0, loop=loop)
        self._reconnecting = False
        if self._reconnect_promise and not self._reconnect_promise.done():
            self._reconnect_promise.cancel()

    async def evaluate_in_page(
        self, js_string: str, contextId: Optional[Any] = None
    ) -> Any:
        """Evaluates the supplied string of JavaScript in the tab

        :param js_string: The string of JavaScript to be evaluated
        :return: The results of the evaluation if any
        """
        logged_method = "evaluate_in_page"
        self.logger.info(logged_method, "evaluating js in page")
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
        self.logger.info(logged_method, f"connecting to the browser {self.tab_data}")
        self.client = await connect(
            self.tab_data["webSocketDebuggerUrl"], remote=True, loop=self.loop
        )

        self.logger.info(logged_method, "connected to browser")

        self.client.on(Client.Events.Disconnected, self._on_connection_closed)
        self.client.Inspector.detached(self.devtools_reconnect)
        self.client.Inspector.targetCrashed(self._on_inspector_crashed)

        await aio_gather(
            self.client.Page.enable(),
            self.client.Network.enable(),
            self.client.Runtime.enable(),
            loop=self.loop,
        )
        self.logger.info(logged_method, "enabled domains")

    async def init(self) -> None:
        """Initialize the client connection to the tab.

        Subclasses are expected to call this method from their
        implementation. This can be the only call in their
        implementation.
        """
        self.logger.info("init", f"running = {self.running}")
        if self._running:
            return
        await self.connect_to_tab()
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
        self.emit(BaseTab.Events.Closed, TabClosedInfo(self.tab_id, self._close_reason))

    async def shutdown_gracefully(self) -> None:
        """Initiates the graceful shutdown of the tab"""
        logged_method = "shutdown_gracefully"
        self.logger.info(logged_method, "shutting down")
        self._graceful_shutdown = True
        await self.close()
        self.logger.info(logged_method, "shutdown complete")

    async def capture_screenshot(self) -> bytes:
        """Capture a screenshot (in png format) of the current page.

        :return: The captured screenshot as bytes
        """
        logged_method = "capture_screenshot"
        self.logger.info(logged_method, "capturing screenshot of page")
        metrics = await self.client.Page.getLayoutMetrics()
        content_size = metrics["contentSize"]
        width = math_ceil(content_size["width"])
        height = math_ceil(content_size["height"])
        await self.client.Emulation.setDeviceMetricsOverride(
            mobile=False,
            width=width,
            height=height,
            deviceScaleFactor=1,
            screenOrientation={'angle': 0, 'type': "portraitPrimary"},
        )
        result = await self.client.Page.captureScreenshot(
            clip={'x': 0, 'y': 0, 'width': width, 'height': height, 'scale': 1},
            format="png",
        )
        await self.client.Emulation.clearDeviceMetricsOverride()
        self.logger.info(logged_method, "captured screenshot of page")
        return b64decode(result.get("data", b""))

    async def capture_and_upload_screenshot(self) -> None:
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
            try:
                config = self.config
                content_type = "image/png"
                async with self.session.put(
                    config.screenshot_api_url,
                    params={
                        "reqid": config.reqid,
                        "target_uri": config.screenshot_target_uri,
                        "content_type": content_type,
                    },
                    data=BytesIO(screen_shot),
                    headers={"content-type": content_type},
                ) as resp:
                    resp.raise_for_status()
            except ClientResponseError as e:
                self.logger.exception(
                    logged_method,
                    "sent the captured screenshot but the server indicates a failure",
                    exc_info=e,
                )
            except Exception as e:
                self.logger.exception(
                    logged_method, "sending the captured screenshot failed", exc_info=e
                )
            else:
                self.logger.info(
                    logged_method,
                    "sent the captured screenshot to the configured endpoint",
                )

    async def _on_inspector_crashed(self, *args: Any, **kwargs: Any) -> None:
        """Listener function for when the target has crashed.

        If the tab is running the close reason will be set to TARGET_CRASHED and
        the tab will be closed
        """
        if self._running:
            self.logger.critical(
                "_on_inspector_crashed",
                f"target crashed while running <url={self._url}>",
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
                f"connection closed while running <url={self._url}>",
            )
            self._close_reason = CloseReason.CONNECTION_CLOSED
            await self.close()

    def __str__(self) -> str:
        name = self.__class__.__name__
        info = f"graceful_shutdown={self._graceful_shutdown}, tab_id={self.tab_id}"
        return f"{name}(url={self._url}, running={self._running} connected={not self._connection_closed}, {info})"

    def __repr__(self) -> str:
        return self.__str__()
