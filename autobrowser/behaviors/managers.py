from asyncio import AbstractEventLoop
from typing import Any, Dict, List, TYPE_CHECKING
from ujson import loads as ujson_loads

from aiofiles import open as aiofiles_open
from attr import dataclass as attr_dataclass, ib as attr_ib
from aiohttp import ClientSession
from urlcanon.rules import MatchRule

from autobrowser.abcs import BehaviorManager
from autobrowser.util import AutoLogger, Helper, create_autologger
from .runners import WRBehaviorRunner

if TYPE_CHECKING:
    from autobrowser.abcs import Behavior, Tab

__all__ = ["BehaviorMatcher", "LocalBehaviorManager", "RemoteBehaviorManager"]


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


@attr_dataclass(slots=True)
class BehaviorMatcher:
    """Combines both the matching of URLs to their behaviors and creating the behaviors
    based on the supplied behavior config.

    The definition for the URL matching behavior, provided by urlcanon.rules.MatchRule,
    is expected to be defined in the "match" key of the behavior_config dictionary. See
    urlcanon.rules.MatchRule for more information.
    """

    behavior_config: Dict = attr_ib()
    matcher: MatchRule = attr_ib(init=False)

    @matcher.default
    def matcher_default(self) -> MatchRule:
        return MatchRule(**self.behavior_config.get("match"))

    def applies(self, url: str) -> bool:
        return self.matcher.applies(url)


@attr_dataclass(slots=True)
class LocalBehaviorManager(BehaviorManager):
    """Manages matching URL to their corresponding behaviors."""

    matchers: List[BehaviorMatcher] = attr_ib()
    default_behavior_init: Dict = attr_ib()
    loop: AbstractEventLoop = attr_ib(default=None)

    async def behavior_for_url(self, url: str, tab: "Tab", **kwargs: Any) -> "Behavior":
        """Retrieve the behavior for the supplied URL, if no behavior's
        url matches then a default behavior is returned.

        :param url: The url to receive the Behavior class for
        :param tab: The browser tab the behavior is to run in
        :return: The Behavior for the URL
        """
        behavior_config = self.default_behavior_init
        for rule in self.matchers:
            if rule.applies(url):
                behavior_config = rule.behavior_config
                break
        async with aiofiles_open(behavior_config.get("resource"), "r") as bjs_in:
            behavior_js = await bjs_in.read()
        return WRBehaviorRunner(
            behavior_js=behavior_js, tab=tab, loop=self.loop, **kwargs
        )

    async def behavior_info_for_url(self, url: str) -> Dict:
        """Retrieve the behavior info for the supplied URL.

        :param url: The url to receive the Behavior class for
        :return: The matched Behavior's info
        """
        behavior_config = self.default_behavior_init
        for rule in self.matchers:
            if rule.applies(url):
                behavior_config = rule.behavior_config
                break
        return behavior_config

    def __attrs_post_init__(self) -> None:
        if self.loop is None:
            self.loop = Helper.event_loop()
