# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import List

from autobrowser.behaviors.behavior_manager import BehaviorManager
from .behaviorTab import BehaviorTab

__all__ = ["CrawlerTab"]

logger = logging.getLogger("autobrowser")


class CrawlerTab(BehaviorTab):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.href_fn = "function () { return this.href; }"

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
                href = results.get('result', {}).get('value')
                if href is not None:
                    outlinks.append(href)
                await self.client.Runtime.releaseObject(objectId=obj_id)
        await self.client.DOM.disable()
