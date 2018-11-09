# -*- coding: utf-8 -*-
import asyncio
import logging
from asyncio import Task, CancelledError
from pathlib import Path
from typing import List, Optional, Any, Union

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
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.href_fn: str = "function () { return this.href; }"
        self.outlink_expression: str = "window.$wbOutlinks$"
        self.frame_manager: FrameManager = None
        self.crawl_loop: Optional[Task] = None
        if self.redis is not None:
            self.frontier: Union[RedisFrontier, Frontier] = RedisFrontier(
                self.redis, self.autoid
            )
        else:
            self.frontier: Union[RedisFrontier, Frontier] = Frontier.init_(
                **kwargs.get("frontier")
            )
        self._max_behavior_time: int = 60

    @classmethod
    def create(cls, *args, **kwargs) -> "CrawlerTab":
        return cls(*args, **kwargs)

    async def init(self) -> None:
        if self._running:
            return
        logger.info("CrawlerTab[init]: initializing")
        await super().init()
        await self.client.Network.setCacheDisabled(True)
        await self.client.Page.setLifecycleEventsEnabled(True)
        frame_tree = await self.client.Page.getFrameTree()
        self.frame_manager = FrameManager(
            self.client, frame_tree["frameTree"], loop=self.loop
        )
        dir_path = Path(__file__).parent
        async with aiofiles.open(str(dir_path / "js" / "nice.js"), "r") as iin:
            await self.client.Page.addScriptToEvaluateOnNewDocument(await iin.read())
        await self.frontier.init()
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

    async def goto(self, url: str, **kwargs: Any) -> bool:
        try:
            await self.main_frame.goto(url, waitUntil="networkidle0")
        except NavigationError as ne:
            logger.exception(f"CrawlerTab[goto]: navigation error for {url}, error msg = {ne}")
            return True
        return False

    async def crawl(self) -> None:
        logger.info("CrawlerTab[crawl]: loop started")
        # loop until frontier is exhausted
        while not await self.frontier.exhausted():
            logger.info("CrawlerTab[crawl]: frontier not exhausted")
            if self._graceful_shutdown:
                logger.info(f"CrawlerTab[crawl]: got graceful_shutdown before crawling the url")
                break
            n_url = await self.frontier.next_url()
            logger.info(f"CrawlerTab[crawl]: navigating to {n_url}")
            was_error = await self.goto(n_url)
            logger.info(f"CrawlerTab[crawl]: navigated to {n_url} with {'an error' if was_error else 'no error'}")
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
                logger.info(f"CrawlerTab[crawl]: got graceful_shutdown after crawling the current url")
                break

    async def manual_collect_outlinks(self):
        await self.client.DOM.enable()
        outlinks: List[str] = list()
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
                    outlinks.append(href)
                await self.client.Runtime.releaseObject(objectId=obj_id)
        await self.client.DOM.disable()

    async def shutdown_gracefully(self) -> None:
        logger.info("CrawlerTab[shutdown_gracefully]: shutting down")
        self._graceful_shutdown = True
        if self.crawl_loop is not None:
            await self.crawl_loop
        await self.close()

    def __str__(self) -> str:
        return f"CrawlerTab(autoid={self.autoid}, url={self.tab_data['url']})"
