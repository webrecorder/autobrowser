from asyncio import (
    AbstractEventLoop,
    TimeoutError as AIOTimeoutError,
    create_subprocess_exec,
)
from asyncio.subprocess import DEVNULL, Process as AIOProcess
from typing import Dict, List, Optional

from async_timeout import timeout
from cripy import CDP, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_URL

from autobrowser.automation import AutomationConfig, BrowserExitInfo
from autobrowser.chrome_browser import Chrome
from autobrowser.errors import DriverError
from autobrowser.util import Helper
from .basedriver import BaseDriver

__all__ = ["LocalBrowserDiver"]


class LocalBrowserDiver(BaseDriver):
    """A driver class for running an automation using browsers installed locally"""

    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        super().__init__(conf, loop)
        self.chrome_process: Optional[AIOProcess] = None
        self.browser: Chrome = None

    def _make_connect_opts(self) -> Dict:
        """Returns a dictionary to be used as the keyword args
        to for CDP methods

        :return: The dictionary to be used as keyword argument
        for CDP methods
        """
        connect = self.conf.chrome_opts.get("connect", {})
        return {
            "frontend_url": connect.get("url", DEFAULT_URL),
            "host": connect.get("host", DEFAULT_HOST),
            "port": connect.get("port", DEFAULT_PORT),
            "secure": connect.get("secure", False),
        }

    async def get_tabs(self) -> List[Dict[str, str]]:
        """Returns a list of tabs in the remote (locally remote) browser

        :return: The list of tabs in the browser
        """
        tabs: List[Dict[str, str]] = []
        tabs_append = tabs.append
        cdp_new_tab = CDP.New
        connect_opts = self._make_connect_opts()
        eloop = self.loop

        ws_url = "webSocketDebuggerUrl"
        page_type = "page"
        type_ = "type"

        for tab in await CDP.List(**connect_opts, loop=eloop):
            if tab[type_] == page_type and ws_url in tab:
                tabs_append(tab)
        for _ in range(self.conf.get("num_tabs") - 1):
            tab = await cdp_new_tab(**connect_opts, loop=eloop)
            tabs.append(tab)
        return tabs

    async def launch_browser(self) -> None:
        """Launches the local browser"""
        chrome_opts = self.conf.chrome_opts
        eloop = self.loop
        self.chrome_process = await create_subprocess_exec(
            chrome_opts["exe"],
            *chrome_opts["args"],
            stderr=DEVNULL,
            stdout=DEVNULL,
            loop=eloop,
        )
        cdp_list = CDP.List
        helper_one_tick_sleep = Helper.one_tick_sleep
        while True:
            try:
                await cdp_list(loop=eloop)
                break
            except Exception:
                await helper_one_tick_sleep()
                pass

    async def init(self) -> None:
        self.logger.info("init", "initializing")
        await super().init()
        if self.conf.chrome_opts.get("launch", False):
            try:
                async with timeout(60):
                    await self.launch_browser()
            except AIOTimeoutError:
                await self.clean_up()
                raise DriverError("Failed To Launch The Browser Within 60 seconds")
        tabs = await self.get_tabs()
        if len(tabs) == 0:
            await self.clean_up()
            raise DriverError("No Tabs Were Found To Connect To")
        self.browser = Chrome(
            config=self.conf,
            behavior_manager=self.behavior_manager,
            session=self.session,
            redis=self.redis,
            loop=self.loop,
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
        self.logger.info("shutdown", "shutting down")
        await self.clean_up()
        self.logger.info("shutdown", "shutdown complete")
        return self.determine_exit_code()

    def on_browser_exit(self, info: BrowserExitInfo) -> None:
        self.logger.info(
            f"on_browser_exit(info={info})", "browser exited shutting down"
        )
        self.browser.remove_all_listeners()
        self.browser = None
        self._browser_exit_infos.append(info)
        self.shutdown_condition.initiate_shutdown()

    def __str__(self) -> str:
        return f"LocalBrowserDiver(browser={self.browser}, conf={self.conf})"
