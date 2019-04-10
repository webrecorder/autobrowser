from asyncio import Task, gather as aio_gather
from enum import Enum, auto
from pathlib import Path
from typing import Any, Awaitable, Dict, List, Optional

from aiofiles import open as aiofiles_open
from simplechrome.errors import NavigationError
from simplechrome.frame_manager import Frame, FrameManager
from simplechrome.network_manager import NetworkManager, Response

from autobrowser.automation import CloseReason, RedisKeys
from autobrowser.frontier import RedisFrontier
from autobrowser.util import Helper
from .basetab import BaseTab

__all__ = ["CrawlerTab"]


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
         - OUTLINKS_EXPRESSION: the JS expression to be used for collecting outlinks
         - CLEAR_OUTLINKS_EXPRESSION: the JS expression to be used for clearing the
           collected outlinks
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        #: Function expression for retrieving fully resolved URLs in manual_collect_outlinks
        self.href_fn: str = "function () { return this.href; }"
        config = self.config
        #: The variable name for the outlinks discovered by running the behavior
        self.collect_outlinks_expression: str = config.outlinks_expression
        self.clear_outlinks_expression: str = config.clear_outlinks_expression
        #: The frame manager for the page
        self.frames: FrameManager = None
        self.network: NetworkManager = None
        self.redis_keys: RedisKeys = RedisKeys(config.autoid)
        #: The crawling main loop
        self.crawl_loop: Optional[Task] = None
        self.frontier: RedisFrontier = RedisFrontier(self.redis, self.redis_keys)
        #: The maximum amount of time the crawler should run behaviors for
        self._max_behavior_time: int = config.max_behavior_time
        self._navigation_timeout: int = config.navigation_timeout
        self._exit_crawl_loop: bool = False

    @classmethod
    def create(cls, *args, **kwargs) -> "CrawlerTab":
        return cls(*args, **kwargs)

    @property
    def main_frame(self) -> Frame:
        """Returns a reference to the current main frame (top) of the tab

        :return: The main frame of the tab
        """
        return self.frames.mainFrame

    def main_frame_getter(self) -> Frame:
        """Helper function for behaviors that returns the current main frame
        of the tab

        :return: The main frame of the tab
        """
        return self.frames.mainFrame

    def wait_for_net_idle(
        self, num_inflight: int = 2, idle_time: int = 2, global_wait: int = 60
    ) -> Awaitable[None]:
        """Returns a future that  resolves once network idle occurs.

        See the options of autobrowser.util.netidle.monitor for a complete
        description of the available arguments
        """
        return self.network.network_idle_promise(
            num_inflight=num_inflight, idle_time=idle_time, global_wait=global_wait
        )

    async def collect_outlinks(self) -> None:
        """Retrieves the outlinks collected by the running behaviors and adds them to the frontier"""
        logged_method = "collect_outlinks"
        out_links = None
        try:
            out_links = await self.evaluate_in_page(self.collect_outlinks_expression)
        except Exception as e:
            self.logger.exception(
                logged_method, "collecting outlinks failed", exc_info=e
            )
        else:
            self.logger.info(logged_method, "collected")

        if out_links is not None:
            try:
                await self.frontier.add_all(out_links)
            except Exception as e:
                self.logger.exception(
                    logged_method, "frontier add_all threw an exception", exc_info=e
                )

        try:
            await self.evaluate_in_page(self.clear_outlinks_expression)
        except Exception as e:
            self.logger.exception(
                logged_method,
                "evaluating clear_outlinks threw an exception",
                exc_info=e,
            )

    async def crawl(self) -> None:
        """Starts the crawl loop.

        For each URL in the frontier:
          - navigate to the page
          - perform the next crawler action based on the navigation results

        The crawl loop is exited once the frontier becomes exhausted or one of the following conditions are met:
           - shutdown, graceful or otherwise, is initiated
           - the connection to the tab is closed
           - navigation to a page fails for unknown reasons
           - the frontier becomes exhausted

        If the crawl loop exits and the exit was not due to graceful shutdown
        the close method is called.
        """
        logged_method = "crawl"
        frontier_exhausted = await self.frontier.exhausted()
        self.logger.info(
            logged_method,
            f"crawl loop starting and the frontier is {'exhausted' if frontier_exhausted else 'not exhausted'}",
        )

        should_exit_crawl_loop = self._should_exit_crawl_loop
        next_crawl_url = self.frontier.next_url
        navigate_to_page = self.goto
        is_frontier_exhausted = self.frontier.exhausted
        log_info = self.logger.info
        handle_navigation_result = self._handle_navigation_result
        one_tick_sleep = Helper.one_tick_sleep

        # loop until frontier is exhausted or we should exit crawl loop
        while 1:
            if frontier_exhausted or should_exit_crawl_loop():
                log_info(
                    logged_method, "exiting crawl loop before crawling the next url"
                )
                break

            next_url = await next_crawl_url()

            log_info(logged_method, f"navigating to {next_url}")

            navigation_result = await navigate_to_page(next_url)

            await handle_navigation_result(next_url, navigation_result)

            if should_exit_crawl_loop():
                log_info(
                    logged_method, "exiting crawl loop after crawling the current url"
                )
                break
            # we sleep for one event loop tick in order to ensure that other
            # coroutines can do their thing if they are waiting. e.g. shutdowns etc
            await one_tick_sleep()
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
        """Navigate the browser to the supplied URL. The return value
        of this function indicates the next action to be performed by the crawler

        :param url: The URL of the page to navigate to
        :param wait: The wait condition that all the pages frame have
        before navigation is considered complete
        :param kwargs: Any additional arguments for use in navigating
        :return: An NavigationResult indicating the next action of the crawler
        """
        self._url = url
        logged_method = f"goto(url={url}, wait={wait})"
        try:
            nav_response = await self.frames.mainFrame.goto(
                url, waitUntil=wait, timeout=self._navigation_timeout
            )
            self.logger.info(
                logged_method, f"we navigated to the page <response={nav_response}>"
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
        """Initialize the crawler tab, if the crawler tab is already running this is a no op."""
        if self._running:
            return
        self.logger.info("init", "initializing")
        # must call super init
        await super().init()
        if self.browser.config.net_cache_disabled:
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
        if self.config.wait_for_q:
            await self.frontier.wait_for_populated_q(self.config.wait_for_q)
        self.crawl_loop = self.loop.create_task(self.crawl())
        self.logger.info("init", "initialized")
        await Helper.one_tick_sleep()

    async def run_behavior(self) -> None:
        """Retrieves the behavior for the page the crawler is currently at and runs it.

        If this method is called and the crawler is to exit the crawl loop this method becomes a no op.

        If the crawler is configured to run behaviors until a configured maximum time, the time_run
        method of autobrowser.behaviors.runners.WRBehaviorRunner is used otherwise run.
        """
        if self._should_exit_crawl_loop():
            return
        logged_method = "run_behavior"
        # use self.frame_manager.mainFrame.url because it is the fully resolved URL that the browser displays
        # after any redirects happen
        self._url = self.main_frame.url
        behavior = await self.behavior_manager.behavior_for_url(
            self.main_frame.url,
            self,
            collect_outlinks=True,
            take_screen_shot=self.config.should_take_screenshot,
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
        """Manually collects outlinks (a[href], area[href]) from the page and all sub frames"""
        self.logger.info("manual_collect_outlinks", "collecting")
        await self.client.DOM.enable()

        out_links: List[str] = []
        promises = []
        add_out_link = out_links.append
        add_extraction_promise = promises.append
        extract_href_from_remote_node = self._extract_href_from_remote_node

        nodes = await self.client.DOM.getFlattenedDocument(depth=-1, pierce=True)
        for node in nodes["nodes"]:
            node_name = node["localName"]
            if node_name == "a" or node_name == "area":
                add_extraction_promise(extract_href_from_remote_node(node))

        results = await aio_gather(*promises, loop=self.loop, return_exceptions=True)
        for result in results:
            if isinstance(result, str) and result:
                add_out_link(result)

        await self.client.DOM.disable()
        await self.frontier.add_all(out_links)

    async def _extract_href_from_remote_node(self, node: Dict) -> Optional[str]:
        runtime_node = await self.client.DOM.resolveNode(nodeId=node["nodeId"])
        obj_id = runtime_node["object"]["objectId"]
        results = await self.client.Runtime.callFunctionOn(
            self.href_fn, objectId=obj_id
        )
        href = results.get("result", {}).get("value")
        await self.client.Runtime.releaseObject(objectId=obj_id)
        return href

    def _crawl_loop_running(self) -> bool:
        """Returns T/F indicating if the crawl loop is running (task not done)

        :return: T/F indicating if crawl loop is running
        """
        return self.crawl_loop is not None and not self.crawl_loop.done()

    def _determine_navigation_result(
        self, navigation_response: Optional[Response]
    ) -> NavigationResult:
        """Returns the NavigationResult based on the supplied navigation response

        :param navigation_response: The navigation response if one was sent
        :return: The NavigationResult based on the navigation response
        """
        logged_method = "_determine_navigation_result"
        if navigation_response is None:
            self.logger.info(
                logged_method,
                f"we navigated somewhere but must skip the URL due to not having a navigation response",
            )
            return NavigationResult.SKIP_URL
        if "html" in navigation_response.mimeType.lower():
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

    async def _handle_navigation_result(
        self, url: str, navigation_result: NavigationResult
    ) -> None:
        """Performs the next crawler action based on the supplied navigation results.

        Actions:
           - `EXIT_CRAWL_LOOP`: log and set the `_exit_crawl_loop` to True
           - `SKIP_URL`: log
           - `OK`: log and run the page's behavior

        The currently crawled URL is always updated in redis no matter what
        the navigation result is.

        :param url: The URL of the page navigated to
        :param navigation_result: The results of the navigation
        """
        logged_method = "_handle_navigation_result"

        if navigation_result == NavigationResult.EXIT_CRAWL_LOOP:
            self.logger.critical(
                logged_method, "exiting crawl loop due to fatal navigation error"
            )
            self._exit_crawl_loop = True
        elif navigation_result == NavigationResult.SKIP_URL:
            self.logger.info(
                logged_method, f"the URL navigated to is being skipped <url={url}>"
            )
        else:
            self.logger.info(
                logged_method, f"navigated to the next URL with no error <url={url}>"
            )

            # maybe run a behavior
            await self.run_behavior()

        await self.frontier.remove_current_from_pending()

    def _should_exit_crawl_loop(self) -> bool:
        """Returns T/F indicating if the crawl loop should be exited based on if
        graceful shutdown was initiated, or the connection to the tab was closed,
        if the exit crawl loop property is set to true

        :return: T/F indicating if the crawl loop should be exited
        """
        return (
            self._graceful_shutdown or self.connection_closed or self._exit_crawl_loop
        )
