# -*- coding: utf-8 -*-
import asyncio
import logging
from asyncio import AbstractEventLoop, Future, Task
from pathlib import Path
from typing import List, Optional, Set

import aiofiles
from async_timeout import timeout
from simplechrome.frame_manager import FrameManager
from simplechrome.navigator_watcher import NavigatorWatcher

from autobrowser.behaviors.basebehavior import Behavior
from autobrowser.behaviors.behavior_manager import BehaviorManager
from autobrowser.frontier import Frontier
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
        self.frontier: Frontier = Frontier.init(**kwargs.get("frontier"))
        self._max_behavior_time: int = 60

    @classmethod
    def create(cls, *args, **kwargs) -> "CrawlerTab":
        return cls(*args, **kwargs)

    async def init(self) -> None:
        if self._running:
            return
        await super().init()
        await self.client.Network.setCacheDisabled(True)
        await self.client.Page.setLifecycleEventsEnabled(True)
        frame_tree = await self.client.Page.getFrameTree()
        self.frame_manager = FrameManager(self.client, frame_tree["frameTree"], None)
        dir_path = Path(__file__).parent
        async with aiofiles.open(str(dir_path / "js" / "nice.js"), "r") as iin:
            await self.client.Page.addScriptToEvaluateOnNewDocument(await iin.read())
        self.crawl_loop = self._loop.create_task(self.crawl())

    async def close(self) -> None:
        await super().close()
        if self.crawl_loop is not None:
            self.crawl_loop.cancel()

    @property
    def frontier_exhausted(self) -> bool:
        return self.frontier.exhausted

    async def navigate(self, url: str) -> None:
        try:
            results = await self.frame_manager.mainFrame.goto(
                url, dict(waitUntil="networkidle0")
            )
        except Exception:
            pass
        print(f"net idle {results}")
        # results = await self.goto(url, transitionType="address_bar")
        # results = await self.goto(n_url)
        # print(f"waiting for net idle {results}")

    async def crawl(self) -> None:
        # loop until frontier is exhausted
        while not self.frontier.exhausted:
            print(self.frontier.queue)
            n_url = self.frontier.pop()
            # navigate to next URL and wait until network idle
            print(f"navigating to {n_url}")
            await self.navigate(n_url)
            # results = await self.goto(n_url, transitionType="address_bar")
            # results = await self.goto(n_url)
            # print(f"waiting for net idle {results}")
            # await self.net_idle(idle_time=2, global_wait=90)
            # print("net idle")
            # get the url of the main (top) frame
            ex_cntx = await self.frame_manager.mainFrame.executionContext()
            behavior = BehaviorManager.behavior_for_url(
                self.frame_manager.mainFrame.url, self, cntx_id=ex_cntx.id
            )
            # print(f"running behavior {behavior}")
            # we have a behavior to be run so run it
            if behavior is not None:
                # run the behavior in a timed fashion (async_timeout will cancel the corutine if max time is reached)
                try:
                    async with timeout(self._max_behavior_time, loop=self._loop):
                        await behavior.run_task(loop=self._loop)
                except asyncio.TimeoutError:
                    print("timed behavior to")
                    pass
            out_links = await self.evaluate_in_page(self.outlink_expression)
            self.frontier.add_all(out_links.get("result", {}).get("value", []))

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
