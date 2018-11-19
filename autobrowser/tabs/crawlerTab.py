import logging
from asyncio import Task, CancelledError, TimeoutError
from pathlib import Path
from typing import List, Optional, Any, Union

import aiofiles
import os
from async_timeout import timeout
from simplechrome.errors import NavigationError
from simplechrome.frame_manager import FrameManager, Frame

from autobrowser.behaviors import BehaviorManager
from autobrowser.frontier import Frontier, RedisFrontier
from .basetab import BaseAutoTab

__all__ = ["CrawlerTab"]

logger = logging.getLogger("autobrowser")


class CrawlerTab(BaseAutoTab):
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
        self.frame_manager: FrameManager = None
        #: The crawling main loop
        self.crawl_loop: Optional[Task] = None
        if self.redis is not None:
            self.frontier: Union[RedisFrontier, Frontier] = RedisFrontier(
                self.redis, self.autoid
            )
        else:
            self.frontier: Union[RedisFrontier, Frontier] = Frontier.init_(
                **kwargs.get("frontier")
            )
        #: The maximum amount of time the crawler should run behaviors for
        self._max_behavior_time: int = int(os.environ.get("BEHAVIOR_RUN_TIME", 60))
        self._navigation_timeout: int = int(os.environ.get("NAV_TO", 30))

    @classmethod
    def create(cls, *args, **kwargs) -> "CrawlerTab":
        return cls(*args, **kwargs)

    async def init(self) -> None:
        """Initialize the crawler tab, if the crawler tab is already
        running this is a no op."""
        if self._running:
            return
        logger.info("CrawlerTab[init]: initializing")
        # must call super init
        await super().init()
        if os.environ.get("CRAWL_NO_NETCACHE", False):
            await self.client.Network.setCacheDisabled(True)
        # enable receiving of frame lifecycle events for the frame manager
        await self.client.Page.setLifecycleEventsEnabled(True)
        frame_tree = await self.client.Page.getFrameTree()
        self.frame_manager = FrameManager(
            self.client, frame_tree["frameTree"], loop=self.loop
        )
        # ensure we do not have any naughty JS by disabling its ability to
        # prevent us from navigating away from the page
        async with aiofiles.open(
            str(Path(__file__).parent / "js" / "nice.js"), "r"
        ) as iin:
            await self.client.Page.addScriptToEvaluateOnNewDocument(await iin.read())
        await self.frontier.init()
        if os.environ.get("WAIT_FOR_Q", False):
            await self.frontier.wait_for_populated_q()
        self.crawl_loop = self.loop.create_task(self.crawl())
        logger.info("CrawlerTab[init]: initialized")

    async def close(self) -> None:
        logger.info("CrawlerTab[close]: closing")
        if self.crawl_loop is not None and not self.crawl_loop.done():
            self.crawl_loop.cancel()
            try:
                await self.crawl_loop
            except CancelledError:
                pass
        await super().close()

    @property
    def main_frame(self) -> Frame:
        return self.frame_manager.mainFrame

    async def goto(
        self, url: str, waitUntil: str = "networkidle0", **kwargs: Any
    ) -> bool:
        """Navigate the browser to the supplied URL.

        :param url: The URL of the page to navigate to
        :param waitUntil: The wait condition that all the pages frame have
        before navigation is considered complete
        :param kwargs: Any additional arguments for use in navigating
        :return: True or False indicating if navigation encountered an error
        """
        try:
            await self.main_frame.goto(
                url, waitUntil=waitUntil, timeout=self._navigation_timeout, **kwargs
            )
        except NavigationError as ne:
            logger.exception(
                f"CrawlerTab[goto]: navigation error for {url}, error msg = {ne}"
            )
            return True
        return False

    async def _report_initial_fstate(self) -> None:
        frontier_state = "" if await self.frontier.exhausted() else "not"
        logger.info(
            f"CrawlerTab[crawl]: crawl loop starting and the frontier is {frontier_state} exhausted"
        )

    async def collect_outlinks(self):
        try:
            out_links = await self.main_frame.evaluate_expression(
                self.outlink_expression
            )
        except Exception as e:
            logger.error(
                f"CrawlerTab[collect_outlinks]: mainFrame.evaluate_expression threw an error falling back to evaluate_in_page. {e}"
            )
            out_links = await self.evaluate_in_page(self.outlink_expression)
        logger.info(f"CrawlerTab[crawl]: collected outlinks")
        if out_links is not None:
            try:
                await self.frontier.add_all(out_links)
            except Exception as e:
                logger.error(f"CrawlerTab[collect_outlinks]: frontier add_all threw an exception {e}")

        try:
            await self.evaluate_in_page(self.clear_outlinks)
        except Exception as e:
            logger.error(f"CrawlerTab[collect_outlinks]: evaluating clear_outlinks threw an exception {e}")

    def main_frame_getter(self) -> Frame:
        return self.frame_manager.mainFrame

    async def crawl(self) -> None:
        await self._report_initial_fstate()
        # loop until frontier is exhausted
        while not await self.frontier.exhausted():
            if self._graceful_shutdown:
                logger.info(
                    f"CrawlerTab[crawl]: got graceful_shutdown before crawling the url"
                )
                break
            n_url = await self.frontier.next_url()
            logger.info(f"CrawlerTab[crawl]: navigating to {n_url}")
            was_error = await self.goto(n_url)
            if was_error:
                error_m = "an error"
            else:
                error_m = "no error"
            logger.info(f"CrawlerTab[crawl]: navigated to {n_url} with {error_m}")
            # use self.frame_manager.mainFrame.url because it is the fully resolved URL that the browser displays
            # after any redirects happen
            behavior = BehaviorManager.behavior_for_url(
                self.main_frame.url, self
            )
            behavior.set_outlink_collection_fn(self.collect_outlinks)
            logger.info(f"CrawlerTab[crawl]: running behavior {behavior}")
            # we have a behavior to be run so run it
            if behavior is not None:
                # run the behavior in a timed fashion (async_timeout will cancel the corutine if max time is reached)
                if self._max_behavior_time != -1:
                    try:
                        async with timeout(self._max_behavior_time, loop=self.loop):
                            await behavior.run()
                    except TimeoutError:
                        logger.info("CrawlerTab[crawl]: timed behavior to")
                        pass
                else:
                    try:
                        await behavior.run()
                    except Exception as e:
                        logger.error(
                            f"CrawlerTab[crawl]: behavior threw an error {e}"
                        )

            if self._graceful_shutdown:
                logger.info(
                    f"CrawlerTab[crawl]: got graceful_shutdown after crawling the current url"
                )
                break
        logger.info("CrawlerTab[crawl]: crawl loop stopped")
        if not self._graceful_shutdown:
            self.emit('crawl-done')

    async def manual_collect_outlinks(self):
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

    async def shutdown_gracefully(self) -> None:
        logger.info("CrawlerTab[shutdown_gracefully]: shutting down")
        self._graceful_shutdown = True
        if self.crawl_loop is not None:
            await self.crawl_loop
        await self.close()

    def __str__(self) -> str:
        return f"CrawlerTab(autoid={self.autoid}, url={self.tab_data['url']})"
