# -*- coding: utf-8 -*-
import asyncio
import logging
from asyncio import AbstractEventLoop, Future
from pathlib import Path
from typing import List, Optional, Set

import aiofiles
from async_timeout import timeout
from simplechrome.frame_manager import FrameManager

from autobrowser.behaviors.basebehavior import Behavior
from autobrowser.behaviors.behavior_manager import BehaviorManager
from .basetab import BaseAutoTab

__all__ = ["CrawlerTab"]

logger = logging.getLogger("autobrowser")


class CrawlerTab(BaseAutoTab):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.href_fn: str = "function () { return this.href; }"
        self.frame_manager: FrameManager = None
        self.crawl_loop: Optional[Future] = None
        self.frontier: Set[str] = set()
        self._outlinks: Optional[str] = None
        self._loop: AbstractEventLoop = asyncio.get_event_loop()
        self._max_behavior_time: int = 60

    @classmethod
    def create(cls, *args, **kwargs) -> "CrawlerTab":
        return cls(*args, **kwargs)

    async def init(self) -> None:
        if self._running:
            return
        await super().init()
        await self.client.Network.setCacheDisabled(True)
        frame_tree = await self.client.Page.getFrameTree()
        self.frame_manager = FrameManager(self.client, frame_tree["frameTree"], None)
        self.crawl_loop = asyncio.ensure_future(
            self.crawl(), loop=asyncio.get_event_loop()
        )
        resource = str(Path(__file__).parent / "js" / "collectOutlinks.js")
        async with aiofiles.open(resource, "r") as iin:
            self._outlinks = await iin.read()

    async def close(self) -> None:
        await super().close()
        if self.crawl_loop is not None:
            self.crawl_loop.cancel()

    @property
    def frontier_size(self) -> int:
        return len(self.frontier)

    async def crawl(self) -> None:
        # loop until frontier is exhausted
        while self.frontier_size > 0:
            n_url = self.frontier.pop()
            # navigate to next URL and wait until network idle
            print(f"navigating to {n_url}")
            results = await self.goto(n_url, transitionType="address_bar")
            print(f'waiting for net idle {results}')
            await self.net_idle(idle_time=2, global_wait=90)
            print('net idle')
            # get the url of the main (top) frame
            mainFrame = self.frame_manager.mainFrame
            # go through all frames in the page we are in
            for frame in self.frame_manager.frames():
                # get the frames JavaScript execution context
                ex_cntx = await frame.executionContext()
                # get outlinks from it
                eval_res = await self.evaluate_in_page(
                    self._outlinks, contextId=ex_cntx.id
                )
                outlinks = eval_res.get("result")
                if outlinks.get("type") == "object":
                    self.frontier.update(outlinks.get("value"))
                # if the frames is the main frame then we get a behavior for it (default or matching)
                if frame.url == mainFrame.url and frame == mainFrame:
                    behavior = BehaviorManager.behavior_for_url(
                        frame.url, self, ex_cntx.id
                    )
                else:
                    # otherwise only get a behavior that matches the URL of the frame exactly
                    behavior = BehaviorManager.behavior_for_url_exact(
                        frame.url, self, ex_cntx.id
                    )
                # we have a behavior to be run so run it
                if behavior is not None:
                    await self._timed_behavior(behavior)
            print('dumping frontier')

    async def _timed_behavior(self, behavior: Behavior) -> None:
        # check to see if the behavior requires resources and if so load them
        if behavior.has_resources:
            await behavior.load_resources()
        # run the behavior in a timed fashion (async_timeout will cancel the corutine if max time is reached)
        try:
            async with timeout(self._max_behavior_time, loop=self._loop):
                while not behavior.done:
                    await behavior.run()
        except asyncio.TimeoutError:
            pass

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

    def __repr__(self) -> str:
        return f"CrawlerTab({self.tab_data}"
