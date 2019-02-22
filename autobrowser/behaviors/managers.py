import logging
from typing import Any, Dict, List, TYPE_CHECKING
from ujson import loads as ujson_loads

import aiofiles
import attr
from aiohttp import ClientSession
from urlcanon.rules import MatchRule

from autobrowser.abcs import BehaviorManager
from .runners import WRBehaviorRunner

if TYPE_CHECKING:
    from autobrowser.abcs import Behavior, Tab

logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True)
class RemoteBehaviorManager(BehaviorManager):
    """Manages matching URL to their corresponding behaviors by
    requesting the behavior from a remote endpoint
    """

    behavior_endpoint: str = attr.ib()
    behavior_info_endpoint: str = attr.ib()
    session: ClientSession = attr.ib()

    async def behavior_for_url(self, url: str, tab: "Tab", **kwargs: Any) -> "Behavior":
        logger.info(
            f"RemoteBehaviorManager[behavior_for_url]: fetching behavior for {url}"
        )
        async with self.session.get(f"{self.behavior_endpoint}{url}") as res:
            logger.info(
                f"RemoteBehaviorManager[behavior_for_url]: fetched behavior for {url}: status = {res.status}"
            )
            behavior_js = await res.text()
            behavior = WRBehaviorRunner(behavior_js=behavior_js, tab=tab, **kwargs)
            return behavior

    async def behavior_info_for_url(self, url: str) -> Dict[str, Any]:
        logger.info(
            f"RemoteBehaviorManager[behavior_for_url]: fetching  behavior info for {url}"
        )
        async with self.session.get(f"{self.behavior_info_endpoint}{url}") as res:
            logger.info(
                f"RemoteBehaviorManager[behavior_for_url]: fetched behavior info for {url}: status = {res.status}"
            )
            info: Dict[str, Any] = await res.json(loads=ujson_loads)
            return info


@attr.dataclass(slots=True)
class BehaviorMatcher:
    """Combines both the matching of URLs to their behaviors and creating the behaviors
    based on the supplied behavior config.

    The definition for the URL matching behavior, provided by urlcanon.rules.MatchRule,
    is expected to be defined in the "match" key of the behavior_config dictionary. See
    urlcanon.rules.MatchRule for more information.
    """

    behavior_config: Dict = attr.ib()
    matcher: MatchRule = attr.ib(init=False)

    @matcher.default
    def matcher_default(self) -> MatchRule:
        return MatchRule(**self.behavior_config.get("match"))

    def applies(self, url: str) -> bool:
        return self.matcher.applies(url)


@attr.dataclass(slots=True)
class LocalBehaviorManager(BehaviorManager):
    """Manages matching URL to their corresponding behaviors."""

    matchers: List[BehaviorMatcher] = attr.ib()
    default_behavior_init: Dict = attr.ib()

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
        async with aiofiles.open(behavior_config.get("resource"), "r") as bjs_in:
            behavior_js = await bjs_in.read()
        return WRBehaviorRunner(behavior_js=behavior_js, tab=tab, **kwargs)

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
