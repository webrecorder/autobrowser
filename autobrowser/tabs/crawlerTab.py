from asyncio import Task
from enum import Enum, auto
from pathlib import Path
from typing import Any, Awaitable, List, Optional, Set

from aiofiles import open as aiofiles_open
from simplechrome.errors import NavigationError
from simplechrome.frame_manager import Frame, FrameManager
from simplechrome.network_manager import NetworkManager, Response

from autobrowser.automation import CloseReason, RedisKeys
from autobrowser.frontier import RedisFrontier
from autobrowser.util import Helper
from .basetab import BaseTab

__all__ = ["CrawlerTab"]


PageMimeTypes: Set[str] = {"text/html"}


class NavigationResult(Enum):
    """An enumeration representing the three possible outcomes of navigation"""
    EXIT_CRAWL_LOOP = auto()
    OK = auto()
    SKIP_URL = auto()


class CrawlerTab(BaseTab):
    """Crawling specific tab.

    Env vars:
         - CRAWL_NO_NETCACHE: if present the network cache is disabled
         - WAIT_FOR_Q: if present the crawler will wait for the frontier q
            to be populated before starting the crawl loop.
         - BEHAVIOR_RUN_TIME: an integer, that if present, will be used
           to set the maximum amount of time the behaviors action will
           be run for (in seconds). If not present the default time
           is 60 seconds
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        #: Function expression for retrieving fully resolved URLs in manual_collect_outlinks
        self.href_fn: str = "function () { return this.href; }"
        #: The variable name for the outlinks discovered by running the behavior
        self.outlink_expression: str = "window.$wbOutlinks$"
        self.clear_outlinks: str = "window.$wbOutlinkSet$.clear()"
        #: The frame manager for the page
        self.frames: FrameManager = None
        self.network: NetworkManager = None
        self.redis_keys: RedisKeys = RedisKeys(self.browser.autoid)
        #: The crawling main loop
        self.crawl_loop: Optional[Task] = None
        self.frontier: RedisFrontier = RedisFrontier(self.redis, self.redis_keys)
        #: The maximum amount of time the crawler should run behaviors for
        self._max_behavior_time: int = self.browser.automation_info.max_behavior_time
        self._navigation_timeout: int = self.browser.automation_info.navigation_timeout

    @classmethod
    def create(cls, *args, **kwargs) -> "CrawlerTab":
        return cls(*args, **kwargs)

    @property
    def main_frame(self) -> Frame:
        return self.frames.mainFrame

    def main_frame_getter(self) -> Frame:
        return self.frames.mainFrame

    def wait_for_net_idle(
        self, num_inflight: int = 2, idle_time: int = 2, global_wait: int = 60
    ) -> Awaitable[None]:
        return self.network.network_idle_promise(
            num_inflight=num_inflight, idle_time=idle_time, global_wait=global_wait
        )

    async def collect_outlinks(self) -> None:
        logged_method = "collect_outlinks"
        try:
            out_links = await self.main_frame.evaluate_expression(
                self.outlink_expression
            )
        except Exception as e:
            self.logger.exception(
                logged_method,
                "mainFrame.evaluate_expression threw an error falling back to evaluate_in_page",
                exc_info=e,
            )
            out_links = await self.evaluate_in_page(self.outlink_expression)

        self.logger.info("crawl", "collected outlinks")

        if out_links is not None:
            try:
                await self.frontier.add_all(out_links)
            except Exception as e:
                self.logger.exception(
                    logged_method, "frontier add_all threw an exception", exc_info=e
                )

        try:
            await self.evaluate_in_page(self.clear_outlinks)
        except Exception as e:
            self.logger.exception(
                logged_method,
                "evaluating clear_outlinks threw an exception",
                exc_info=e,
            )

    async def crawl(self) -> None:
        logged_method = "crawl"
        frontier_exhausted = await self.frontier.exhausted()
        self.logger.info(
            logged_method,
            f"crawl loop starting and the frontier is {'exhausted' if frontier_exhausted else 'not exhausted'}",
        )

        helper_one_tick_sleep = Helper.one_tick_sleep
        log_info = self.logger.info
        log_critical = self.logger.critical
        goto = self.goto
        run_behavior = self.run_behavior
        should_exit_crawl_loop = self._should_exit_crawl_loop
        next_crawl_url = self.frontier.next_url
        indicate_url_crawled = self.frontier.remove_current_from_pending
        is_frontier_exhausted = self.frontier.exhausted

        # loop until frontier is exhausted
        while 1:
            if frontier_exhausted or should_exit_crawl_loop():
                log_info(
                    logged_method, "exiting crawl loop before crawling the next url"
                )
                break

            n_url = await next_crawl_url()
            log_info(logged_method, f"navigating to {n_url}")

            navigation_result = await goto(n_url)

            if navigation_result == NavigationResult.EXIT_CRAWL_LOOP:
                log_critical(
                    logged_method, "exiting crawl loop due to fatal navigation error"
                )
                break

            if navigation_result != NavigationResult.SKIP_URL:
                log_info(
                    logged_method,
                    f"navigated to the next url with no error <url={n_url}>",
                )

                # maybe run a behavior
                await run_behavior()
                await indicate_url_crawled()
            else:
                log_info(
                    logged_method,
                    f"the URL navigated to is being skipped <url={n_url}>",
                )

            if should_exit_crawl_loop():
                log_info(
                    logged_method, "exiting crawl loop after crawling the current url"
                )
                break
            # we sleep for one event loop tick in order to ensure that other
            # coroutines can do their thing if they are waiting. e.g. shutdowns etc
            await helper_one_tick_sleep()
            frontier_exhausted = await is_frontier_exhausted()

        self.logger.info(logged_method, "crawl is finished")
        if not self._graceful_shutdown:
            await self.close()

    async def close(self) -> None:
        logged_method = "close"
        self.logger.info(
            logged_method, f"closing {'gracefully' if self._graceful_shutdown else ''}"
        )
        if self._running_behavior is not None:
            self.logger.info(logged_method, "ending the running behavior")
            self._running_behavior.end()
        if self._crawl_loop_running():
            if not self._graceful_shutdown:
                self.logger.info(logged_method, "canceling the crawl loop task")
            self.logger.info(logged_method, "waiting for the crawl loop task to end")
            try:
                await Helper.timed_future_completion(
                    self.crawl_loop,
                    timeout=15,
                    cancel=not self._graceful_shutdown,
                    loop=self.loop,
                )
            except Exception as e:
                self.logger.exception(
                    logged_method,
                    "the crawl loop threw an unexpected exception while waiting for it to end",
                    exc_info=e,
                )
        self.logger.info(logged_method, "crawl loop task ended")
        self.crawl_loop = None
        is_frontier_exhausted = await self.frontier.exhausted()
        if self._close_reason is None and is_frontier_exhausted:
            self._close_reason = CloseReason.CRAWL_END
        await self.redis.sadd(self.redis_keys.auto_done, self.browser.reqid)
        await super().close()

    async def goto(
        self, url: str, wait: str = "load", *args: Any, **kwargs: Any
    ) -> NavigationResult:
        """Navigate the browser to the supplied URL.

        :param url: The URL of the page to navigate to
        :param wait: The wait condition that all the pages frame have
        before navigation is considered complete
        :param kwargs: Any additional arguments for use in navigating
        :return: True if navigation happened ok or False to indicate all stop
        """
        self._url = url
        logged_method = f"goto(url={url}, wait={wait})"
        try:
            nav_response = await self.frames.mainFrame.goto(
                url, waitUntil=wait, timeout=self._navigation_timeout
            )
            self.logger.info(
                logged_method,
                f"we navigated to the page <response={nav_response}>",
            )
            return self._determine_navigation_result(nav_response)
        except NavigationError as ne:
            if ne.disconnected:
                self.logger.critical(
                    logged_method,
                    f"connection closed while navigating to {url}",
                    exc_info=ne,
                )
                return NavigationResult.EXIT_CRAWL_LOOP
            if ne.timeout or ne.response is not None:
                return self._determine_navigation_result(ne.response)
            self.logger.exception(
                logged_method, f"navigation failed for {url}", exc_info=ne
            )
            return NavigationResult.SKIP_URL
        except Exception as e:
            self.logger.exception(
                logged_method, f"unknown error while navigating to {url}", exc_info=e
            )
            return NavigationResult.EXIT_CRAWL_LOOP

    async def init(self) -> None:
        """Initialize the crawler tab, if the crawler tab is already
        running this is a no op."""
        if self._running:
            return
        self.logger.info("init", "initializing")
        # must call super init
        await super().init()
        if self.browser.automation_info.net_cache_disabled:
            await self.client.Network.setCacheDisabled(True)
        # enable receiving of frame lifecycle events for the frame manager
        await self.client.Page.setLifecycleEventsEnabled(True)
        self.network = NetworkManager(self.client, loop=self.loop)
        frame_tree = await self.client.Page.getFrameTree()
        self.frames = FrameManager(
            self.client,
            frame_tree["frameTree"],
            networkManager=self.network,
            isolateWorlds=False,
            loop=self.loop,
        )
        self.network.setFrameManager(self.frames)
        self.frames.setDefaultNavigationTimeout(self._navigation_timeout)
        # ensure we do not have any naughty JS by disabling its ability to
        # prevent us from navigating away from the page
        async with aiofiles_open(
            str(Path(__file__).parent / "js" / "nice.js"), "r"
        ) as iin:
            await self.client.Page.addScriptToEvaluateOnNewDocument(await iin.read())
        await self.frontier.init()
        if self.browser.automation_info.wait_for_q:
            await self.frontier.wait_for_populated_q(
                self.browser.automation_info.wait_for_q
            )
        self.crawl_loop = self.loop.create_task(self.crawl())
        self.logger.info("init", "initialized")
        await Helper.one_tick_sleep()

    async def run_behavior(self) -> None:
        # use self.frame_manager.mainFrame.url because it is the fully resolved URL that the browser displays
        # after any redirects happen
        if self._should_exit_crawl_loop():
            return
        logged_method = "run_behavior"
        self._url = self.main_frame.url
        behavior = await self.behavior_manager.behavior_for_url(
            self.main_frame.url, self, collect_outlinks=True
        )
        self.logger.info(logged_method, f"running behavior {behavior}")
        # we have a behavior to be run so run it
        if behavior is not None:
            # run the behavior in a timed fashion (async_timeout will cancel the corutine if max time is reached)
            try:
                if self._max_behavior_time != -1:
                    self.logger.info(
                        logged_method,
                        f"running the behavior timed <time={self._max_behavior_time}>",
                    )
                    await behavior.timed_run(self._max_behavior_time)
                else:
                    await behavior.run()
            except Exception as e:
                self.logger.exception(
                    logged_method,
                    "while running the behavior it raised an error",
                    exc_info=e,
                )

    async def manual_collect_outlinks(self) -> None:
        await self.client.DOM.enable()
        out_links: List[str] = list()
        nodes = await self.client.DOM.getFlattenedDocument(depth=-1, pierce=True)
        for node in nodes["nodes"]:
            node_name = node["localName"]
            if node_name == "a" or node_name == "area":
                runtime_node = await self.client.DOM.resolveNode(nodeId=node["nodeId"])
                obj_id = runtime_node["object"]["objectId"]
                results = await self.client.Runtime.callFunctionOn(
                    self.href_fn, objectId=obj_id
                )
                href = results.get("result", {}).get("value")
                if href is not None:
                    out_links.append(href)
                await self.client.Runtime.releaseObject(objectId=obj_id)
        await self.client.DOM.disable()
        await self.frontier.add_all(out_links)

    def _crawl_loop_running(self) -> bool:
        return self.crawl_loop is not None and not self.crawl_loop.done()

    def _determine_navigation_result(
        self, navigation_response: Optional[Response]
    ) -> NavigationResult:
        logged_method = "_determine_navigation_result"
        if navigation_response is None:
            self.logger.info(
                logged_method,
                f"we navigated somewhere but must skip the URL due to not having a navigation response",
            )
            return NavigationResult.SKIP_URL
        if navigation_response.mimeType in PageMimeTypes:
            if navigation_response.ok:
                return NavigationResult.OK
            self.logger.info(
                logged_method,
                f"we navigated to a page but the status was not OK <status={navigation_response.status}>",
            )
            return NavigationResult.SKIP_URL
        self.logger.info(
            logged_method,
            f"we navigated to a non-page <mime={navigation_response.mimeType}, status={navigation_response.status}>",
        )
        return NavigationResult.SKIP_URL

    def _should_exit_crawl_loop(self) -> bool:
        return self._graceful_shutdown or self.connection_closed
