from asyncio import AbstractEventLoop
from typing import Any, Dict, TYPE_CHECKING
from ujson import loads as ujson_loads

from aiohttp import ClientSession
from attr import dataclass as attr_dataclass, ib as attr_ib

from autobrowser.abcs import BehaviorManager
from autobrowser.util import AutoLogger, Helper, create_autologger
from .runners import WRBehaviorRunner

if TYPE_CHECKING:
    from autobrowser.abcs import Behavior, Tab

__all__ = ["RemoteBehaviorManager"]


@attr_dataclass(slots=True)
class RemoteBehaviorManager(BehaviorManager):
    """Manages matching URL to their corresponding behaviors by requesting
    the behavior from a remote endpoint
    """

    behavior_endpoint: str = attr_ib()
    behavior_info_endpoint: str = attr_ib()
    session: ClientSession = attr_ib(repr=False)
    loop: AbstractEventLoop = attr_ib(default=None, repr=False)
    logger: AutoLogger = attr_ib(init=False, default=None, repr=False)

    async def behavior_for_url(self, url: str, tab: "Tab", **kwargs: Any) -> "Behavior":
        self.logger.info("behavior_for_url", f"fetching behavior for {url}")
        async with self.session.get(f"{self.behavior_endpoint}{url}") as res:
            res.raise_for_status()
            self.logger.info(
                "behavior_for_url", f"fetched behavior for {url}: status = {res.status}"
            )
            behavior_js = await res.text()
            behavior = WRBehaviorRunner(
                behavior_js=behavior_js, tab=tab, loop=self.loop, **kwargs
            )
            return behavior

    async def behavior_info_for_url(self, url: str) -> Dict[str, Any]:
        self.logger.info("behavior_info_for_url", f"fetching behavior info for {url}")
        async with self.session.get(f"{self.behavior_info_endpoint}{url}") as res:
            res.raise_for_status()
            self.logger.info(
                "behavior_info_for_url", f"fetched behavior info for {url}: status = {res.status}"
            )
            info: Dict[str, Any] = await res.json(loads=ujson_loads)
            return info

    def __attrs_post_init__(self) -> None:
        if self.loop is None:
            self.loop = Helper.event_loop()
        self.logger = create_autologger(
            "remoteBehaviorManager", "RemoteBehaviorManager"
        )
