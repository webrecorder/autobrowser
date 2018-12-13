import asyncio
import logging
from asyncio import AbstractEventLoop
from asyncio.subprocess import Process
from typing import Optional, Dict, List

from async_timeout import timeout
from cripy import Client, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_URL

from autobrowser.automation import AutomationInfo
from autobrowser.browser import Browser
from autobrowser.errors import DriverError
from autobrowser.automation import AutomationConfig
from .basedriver import Driver

logger = logging.getLogger("autobrowser")

__all__ = ["LocalBrowserDiver"]


class LocalBrowserDiver(Driver):
    """A driver class for running an automation using browsers installed locally"""
    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.chrome_process: Optional[Process] = None
        self.browser: Browser = None

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
        for tab in await Client.List(**connect_opts):
            if tab["type"] == "page" and "webSocketDebuggerUrl" in tab:
                tabs.append(tab)
        for _ in range(self.conf.get("num_tabs") - 1):
            tab = await Client.New(**connect_opts)
            tabs.append(tab)
        return tabs

    async def launch_browser(self) -> None:
        chrome_opts = self.conf.get("chrome_opts")
        self.chrome_process = await asyncio.create_subprocess_exec(
            chrome_opts["exe"],
            *chrome_opts["args"],
            stderr=asyncio.subprocess.PIPE,
            loop=self.loop,
        )
        while True:
            line = await self.chrome_process.stderr.readline()
            if b"DevTools listening on" in line:
                print(line)
                break

    async def init(self) -> None:
        logger.info(f"{self._class_name}[init]: initializing")
        await super().init()
        if self.conf.get("chrome_opts").get("launch", False):
            try:
                async with timeout(60):
                    await self.launch_browser()
            except asyncio.TimeoutError:
                await self.shutdown()
                raise DriverError("Failed To Launch The Browser Within 60 seconds")
        tabs = await self.get_tabs()
        if len(tabs) == 0:
            await self.shutdown()
            raise DriverError("No Tabs Were Found To Connect To")
        self.browser = Browser(
            info=AutomationInfo(
                autoid=self.conf.get("autoid"), tab_type=self.conf.get("tab_type")
            ),
            loop=self.loop,
            redis=self.redis,
            sd_condition=self.shutdown_condition,
        )
        await self.browser.init(tabs)

    async def run(self) -> None:
        logger.info("LocalBrowserDiver[run]: starting")
        if not self.did_init:
            await self.init()
        logger.info("LocalBrowserDiver[run]: waiting for shutdown")
        await self.shutdown_condition
        logger.info(f"LocalBrowserDiver[run]: shutdown condition met")
        await self.shutdown()

    async def shutdown(self) -> None:
        logger.info("LocalBrowserDiver[run]: shutting down")
        if self.browser is not None:
            await self.browser.shutdown_gracefully()
        if self.chrome_process is not None:
            try:
                self.chrome_process.terminate()
                await self.chrome_process.wait()
            except ProcessLookupError:
                pass
        await super().clean_up()
        logger.info("LocalBrowserDiver[run]: shutdown complete")

    def on_browser_exit(self, info: AutomationInfo) -> None:
        logger.info(f"LocalBrowserDiver[on_browser_exit(info={info})]: browser exited shutting down")
        self.shutdown_condition.initiate_shutdown()

