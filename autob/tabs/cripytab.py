import asyncio

from cripy.asyncio import Client
from simplechrome.frame_manager import FrameManager
from pyee import EventEmitter
from .basetab import BaseAutoTab

__all__ = ["CripyAutoTab"]


def is_jsfunc(func: str) -> bool:
    """Huristically check function or expression."""
    func = func.strip()
    if func.startswith("function") or func.startswith("async "):
        return True
    elif "=>" in func:
        return True
    return False


class CripyAutoTab(BaseAutoTab):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frameManager = None

    async def init(self) -> None:
        self.client: Client = await Client(self.tab_data["webSocketDebuggerUrl"])
        self.client.set_close_callback(lambda: self.emit("connection-closed"))

        self.client.Inspector.detached(self.devtools_reconnect)
        self.client.Inspector.targetCrashed(lambda: self.emit("target-crashed"))

        await self.client.Page.enable()
        frameTree = await self.client.Page.getFrameTree()

        await asyncio.gather(
            self.client.Page.setLifecycleEventsEnabled(enabled=True),
            self.client.Network.enable(),
            self.client.Runtime.enable(),
        )

        self.frameManager = FrameManager(self.client, frameTree["frameTree"], None)

        if self.running:
            return
        await super().init()

    async def close(self) -> None:
        if self.client:
            await self.client.dispose()
            self.client = None
        await super().close()

    async def evaluate_in_page(self, js_string: str):
        return await self.client.Runtime.evaluate(
            js_string, userGesture=True, awaitPromise=True
        )

    def __repr__(self):
        return "CripyAutoTab"
