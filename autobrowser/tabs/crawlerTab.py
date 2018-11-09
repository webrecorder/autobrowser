# -*- coding: utf-8 -*-
import asyncio
import logging
from asyncio import Task, CancelledError
from pathlib import Path
from typing import List, Optional, Any, Union
import os
import aiofiles
from async_timeout import timeout
from simplechrome.errors import NavigationError
from simplechrome.frame_manager import FrameManager, Frame

from autobrowser.behaviors.behavior_manager import BehaviorManager
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
            await self.main_frame.goto(url, waitUntil=waitUntil, **kwargs)
        except NavigationError as ne:
            logger.exception(
                f"CrawlerTab[goto]: navigation error for {url}, error msg = {ne}"
            )
            return True
        return False

    async def crawl(self) -> None:
        logger.info(
            f"CrawlerTab[crawl]: crawl loop starting and the frontier is "
            f"{'' if await self.frontier.exhausted() else 'not'} exhausted"
        )
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
            logger.info(
                f"CrawlerTab[crawl]: navigated to {n_url} with {'an error' if was_error else 'no error'}"
            )
            # use self.frame_manager.mainFrame.url because it is the fully resolved URL that the browser displays
            # after any redirects happen
            main_frame = self.frame_manager.mainFrame
            behavior = BehaviorManager.behavior_for_url(
                main_frame.url, self, frame=main_frame
            )
            logger.info(f"CrawlerTab[crawl]: running behavior {behavior}")
            # we have a behavior to be run so run it
            if behavior is not None:
                # run the behavior in a timed fashion (async_timeout will cancel the corutine if max time is reached)
                try:
                    async with timeout(self._max_behavior_time, loop=self.loop):
                        await behavior.run()
                except asyncio.TimeoutError:
                    logger.info("CrawlerTab[crawl]: timed behavior to")
                    pass
            out_links = await main_frame.evaluate_expression(self.outlink_expression)
            logger.info(f"CrawlerTab[crawl]: collected outlinks")
            await self.frontier.add_all(out_links)
            if self._graceful_shutdown:
                logger.info(
                    f"CrawlerTab[crawl]: got graceful_shutdown after crawling the current url"
                )
                break
        logger.info("CrawlerTab[crawl]: crawl loop stopped")

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
