from asyncio import AbstractEventLoop
from collections import Counter
from operator import itemgetter
from typing import Counter as CounterT, List, Optional

from aiohttp import ClientSession
from aioredis import Redis, create_redis_pool

from autobrowser.abcs import Driver
from autobrowser.automation import AutomationConfig, BrowserExitInfo, ShutdownCondition
from autobrowser.behaviors import RemoteBehaviorManager
from autobrowser.chrome_browser import Chrome
from autobrowser.events import Events
from autobrowser.util import AutoLogger, Helper, create_autologger

__all__ = ["BaseDriver"]


class BaseDriver(Driver):
    """An abstract driver class that provides a basic implementation for running an automation"""

    def __init__(
        self, conf: AutomationConfig, loop: Optional[AbstractEventLoop] = None
    ) -> None:
        """Create a new driver

        :param conf: The automation configuration object
        :param loop: The event loop to be used
        """
        self.conf: AutomationConfig = conf
        self.loop: AbstractEventLoop = Helper.ensure_loop(loop)
        self.did_init: bool = False
        self.shutdown_condition: ShutdownCondition = ShutdownCondition(loop=self.loop)
        self.session: ClientSession = Helper.create_aio_http_client_session(loop)
        self.behavior_manager: RemoteBehaviorManager = RemoteBehaviorManager(
            conf=self.conf, session=self.session, loop=self.loop
        )
        self.redis: Redis = None
        self.logger: AutoLogger = create_autologger("drivers", self.__class__.__name__)
        self._browser_exit_infos: List[BrowserExitInfo] = []

    async def init(self) -> None:
        """Initialize the driver."""
        logged_method = "init"
        redis_url = self.conf.redis_url
        self.logger.info(logged_method, f"connecting to redis <url={redis_url}>")
        self.did_init = True
        self.redis = await create_redis_pool(
            redis_url, loop=self.loop, encoding="utf-8"
        )
        self.logger.info(logged_method, f"connected to redis <url={redis_url}>")

        self.logger.info(logged_method, "checking for browser overrides")
        loaded_overrides = await self.conf.load_browser_overrides(self.redis)
        if loaded_overrides:
            self.logger.info(
                logged_method,
                f"we have browser overrides, loaded them - {self.conf.browser_overrides}",
            )
        else:
            self.logger.info(logged_method, "we do not have browser overrides")

    async def clean_up(self) -> None:
        """Performs any necessary cleanup Close all dependant resources.

        This method should be called from subclasses shutdown.
        """
        logged_method = "clean_up"

        if self.redis is not None:
            self.logger.info(logged_method, "closing redis connection")
            self.redis.close()
            await Helper.no_raise_await(self.redis.wait_closed())
            self.logger.info(logged_method, "closed redis connection")

        if not self.session.closed:
            self.logger.info(logged_method, "closing HTTP session")
            await Helper.no_raise_await(self.session.close())
            self.logger.info(logged_method, "closed HTTP session")

        # ensure all underlying connections are closed
        await Helper.one_tick_sleep()
        self.redis = None
        self.behavior_manager = None
        self.session = None

    async def run(self) -> int:
        """Start running the driver.

        Subclasses should not override this method rather override
        one of the lifecycle methods

        Lifecycle methods called:
          - await init
          - await shutdown_condition
          - await shutdown
        """
        self.logger.info("run", "running")
        if not self.did_init:
            await self.init()
        self.logger.info("run", "waiting for shutdown")
        await self.shutdown_condition
        self.logger.info("run", "shutdown condition met")
        return await self.shutdown()

    async def gracefully_shutdown_browser(self, browser: Chrome) -> None:
        """Gracefully shutdowns a browser and adds its exit info to
        the list of browser exit infos.

        :param browser: The browser to gracefully shutdown
        """
        browser.remove_all_listeners()
        future_exit_info = self.loop.create_future()
        browser.once(
            Events.BrowserExiting, lambda info: future_exit_info.set_result(info)
        )
        await browser.shutdown_gracefully()
        self._browser_exit_infos.append(await future_exit_info)

    def determine_exit_code(self) -> int:
        """Determines the exit code based on the exit info's of the browsers.

        If the shutdown condition was met by signal the return value is 1.

        If there were no browser exit info's the return value is 0.

        If there was one browser exit info then the return value is
        the results of calling `BrowserExitInfo.exit_reason_code()`

        Otherwise the return value is `BrowserExitInfo.exit_reason_code()`
        that was seen the most times.

        :return: An exit code based on the exit info's of the browsers
        """
        logged_method = "determine_exit_code"
        if self.shutdown_condition.shutdown_from_signal:
            self.logger.info(logged_method, "exit code 1, shutdown from signal")
            return 1
        beis_len = len(self._browser_exit_infos)
        if beis_len == 0:
            self.logger.info(logged_method, "exit code 0, no browser exit info")
            return 0
        elif beis_len == 1:
            self.logger.info(logged_method, "1 browser exit info, using its exit code")
            return self._browser_exit_infos[0].exit_reason_code()
        self.logger.info(
            logged_method, f"{beis_len} browser exit infos, using their exit code"
        )
        browser_exit_counter: CounterT[int] = Counter()
        for bei in self._browser_exit_infos:
            browser_exit_counter[bei.exit_reason_code()] += 1
        exit_code, count = max(browser_exit_counter.items(), key=itemgetter(1))
        return exit_code

    def initiate_shutdown(self) -> None:
        """Initiate the complete shutdown of the driver (running automation).

        This method should be used to shutdown (stop) the driver from running
        rather than calling :func:`~basedriver.Driver.shutdown` directly
        """
        self.logger.info("initiate_shutdown", "shutdown initiated")
        self.shutdown_condition.initiate_shutdown()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(conf={self.conf})"

    def __repr__(self) -> str:
        return self.__str__()
