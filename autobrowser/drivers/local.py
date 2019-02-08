import asyncio
import logging
from asyncio import AbstractEventLoop
from asyncio.subprocess import Process
from typing import Optional, Dict, List

from async_timeout import timeout
from cripy import CDP, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_URL

from autobrowser.automation import AutomationConfig, AutomationInfo, BrowserExitInfo
from autobrowser.chrome_browser import Chrome
from autobrowser.errors import DriverError
from .basedriver import BaseDriver

logger = logging.getLogger("autobrowser")

__all__ = ["LocalBrowserDiver"]


class LocalBrowserDiver(BaseDriver):
    """A driver class for running an automation using browsers installed locally"""

    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.chrome_process: Optional[Process] = None
        self.browser: Chrome = None

    def _make_connect_opts(self) -> Dict:
        connect = self.conf.get("chrome_opts").get("connect", {})
        return dict(
            frontend_url=connect.get("url", DEFAULT_URL),
            host=connect.get("host", DEFAULT_HOST),
            port=connect.get("port", DEFAULT_PORT),
            secure=connect.get("secure", False),
        )

    async def get_tabs(self) -> List[Dict[str, str]]:
        tabs: List[Dict[str, str]] = []
        connect_opts = self._make_connect_opts()
        for tab in await CDP.List(**connect_opts, loop=self.loop):
            if tab["type"] == "page" and "webSocketDebuggerUrl" in tab:
                tabs.append(tab)
        for _ in range(self.conf.get("num_tabs") - 1):
            tab = await CDP.New(**connect_opts, loop=self.loop)
            tabs.append(tab)
        return tabs

    async def launch_browser(self) -> None:
        chrome_opts = self.conf.get("chrome_opts")
        self.chrome_process = await asyncio.create_subprocess_exec(
            chrome_opts["exe"],
            *chrome_opts["args"],
            stderr=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            loop=self.loop,
        )
        while True:
            try:
                await CDP.List()
                break
            except Exception:
                await asyncio.sleep(0)
                pass

    async def init(self) -> None:
        logger.info(f"{self._class_name}[init]: initializing")
        await super().init()
        if self.conf.get("chrome_opts").get("launch", False):
            try:
                async with timeout(60):
                    await self.launch_browser()
            except asyncio.TimeoutError:
                await self.clean_up()
                raise DriverError("Failed To Launch The Browser Within 60 seconds")
        tabs = await self.get_tabs()
        if len(tabs) == 0:
            await self.clean_up()
            raise DriverError("No Tabs Were Found To Connect To")
        self.browser = Chrome(
            info=AutomationInfo(
                autoid=self.conf.get("autoid", ""),
                reqid=self.conf.get("reqid", ""),
                tab_type=self.conf.get("tab_type"),
                behavior_manager=self.behavior_manager,
            ),
            loop=self.loop,
            redis=self.redis,
        )
        self.browser.on(Chrome.Events.Exiting, self.on_browser_exit)
        await self.browser.init(tabs)

    async def clean_up(self) -> None:
        if self.browser is not None:
            await self.gracefully_shutdown_browser(self.browser)
            self.browser = None

        if self.chrome_process is not None:
            try:
                self.chrome_process.kill()
                await self.chrome_process.wait()
            except ProcessLookupError:
                pass
            self.chrome_process = None
        await super().clean_up()

    async def shutdown(self) -> int:
        logger.info("LocalBrowserDiver[run]: shutting down")
        await self.clean_up()
        logger.info("LocalBrowserDiver[run]: shutdown complete")
        return self.determine_exit_code()

    def on_browser_exit(self, info: BrowserExitInfo) -> None:
        logger.info(
            f"LocalBrowserDiver[on_browser_exit(info={info})]: browser exited shutting down"
        )
        self.browser.remove_all_listeners()
        self.browser = None
        self._browser_exit_infos.append(info)
        self.shutdown_condition.initiate_shutdown()
