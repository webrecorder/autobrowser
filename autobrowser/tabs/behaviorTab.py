# -*- coding: utf-8 -*-
import asyncio
from typing import Optional, Dict, Any

from cripy import connect

from .basetab import BaseAutoTab
from ..logger import logger

__all__ = ["BehaviorTab"]


class BehaviorTab(BaseAutoTab):
    async def init(self) -> None:
        if self._running:
            return
        logger.debug("BehaviorTab.init")
        self._running = True
        self.client = await connect(self.tab_data["webSocketDebuggerUrl"], remote=True)
        logger.debug("BehaviorTab.init connected")
        self.client.set_close_callback(lambda: self.emit("connection-closed"))

        self.client.Inspector.detached(self.devtools_reconnect)
        self.client.Inspector.targetCrashed(lambda: self.emit("target-crashed"))

        await asyncio.gather(
            self.client.Page.enable(),
            self.client.Network.enable(),
            self.client.Runtime.enable(),
        )

        logger.debug("BehaviorTab.init enabled domains")

        self.all_behaviors = asyncio.ensure_future(
            self._behavior_loop(), loop=asyncio.get_event_loop()
        )

    async def _behavior_loop(self):
        logger.debug("BehaviorTab._behavior_loop running")
        while True:
            for behavior in self.behaviors:
                await behavior.run()
            await asyncio.sleep(1)

    async def close(self) -> None:
        if self.client:
            await self.client.dispose()
            self.client = None
        await super().close()

    async def evaluate_in_page(self, js_string: str):
        return await self.client.Runtime.evaluate(
            js_string, userGesture=True, awaitPromise=True
        )

    async def goto(self, url: str, options: Optional[Dict] = None, **kwargs: Any):
        pass

    def __repr__(self):
        return "BehaviorTab"
