from asyncio import AbstractEventLoop
from typing import Any, Dict, Optional, TYPE_CHECKING

from aiohttp import ClientSession
from ujson import loads

from autobrowser.abcs import BehaviorManager
from autobrowser.automation import AutomationConfig
from autobrowser.util import AutoLogger, Helper, create_autologger
from .runners import WRBehaviorRunner

if TYPE_CHECKING:
    from autobrowser.abcs import Behavior, Tab

__all__ = ["RemoteBehaviorManager"]


class RemoteBehaviorManager(BehaviorManager):
    """Manages matching URL to their corresponding behaviors by requesting
    the behavior from a remote endpoint
    """

    __slots__ = ["__weakref__", "conf", "logger", "loop", "session"]

    def __init__(
        self,
        conf: AutomationConfig,
        session: ClientSession,
        loop: Optional[AbstractEventLoop] = None,
    ) -> None:
        """Initialize the new instance of RemoteBehaviorManager

        :param conf: The automation's config
        :param session: The HTTP session to use for making the behavior requests
        :param loop: The event loop for the automation
        """
        self.conf: AutomationConfig = conf
        self.session: ClientSession = session
        self.loop: AbstractEventLoop = Helper.ensure_loop(loop)
        self.logger: AutoLogger = create_autologger(
            "remoteBehaviorManager", "RemoteBehaviorManager"
        )

    async def behavior_for_url(self, url: str, tab: "Tab", **kwargs: Any) -> "Behavior":
        self.logger.info("behavior_for_url", f"fetching behavior - {url}")
        async with self.session.get(self.conf.retrieve_behavior_url(url)) as res:
            self.logger.info(
                "behavior_for_url",
                f"fetched behavior - {{'url': '{url}', 'status': {res.status}}}",
            )
            res.raise_for_status()
            behavior_js = await res.text()
            behavior = WRBehaviorRunner(
                behavior_js=behavior_js,
                tab=tab,
                next_action_expression=self.conf.behavior_action_expression,
                loop=self.loop,
                **kwargs,
            )
            return behavior

    async def behavior_info_for_url(self, url: str) -> Dict[str, Any]:
        self.logger.info("behavior_info_for_url", f"fetching behavior info for {url}")
        async with self.session.get(self.conf.behavior_info_url(url)) as res:
            self.logger.info(
                "behavior_info_for_url",
                f"fetched behavior info - {{'url': '{url}', 'status': {res.status}}}",
            )
            res.raise_for_status()
            info: Dict[str, Any] = await res.json(loads=loads)
            return info

    def __str__(self) -> str:
        info = f"behavior={self.conf.fetch_behavior_endpoint}, info={self.conf.fetch_behavior_info_endpoint}"
        return f"RemoteBehaviorManager({info})"

    def __repr__(self) -> str:
        return self.__str__()
