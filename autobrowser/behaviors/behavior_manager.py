# -*- coding: utf-8 -*-
import logging
from importlib import import_module
from pathlib import Path
from typing import Dict, List, Optional, Type, TYPE_CHECKING, Tuple, Any

import attr
from ruamel.yaml import YAML
from urlcanon.rules import MatchRule

if TYPE_CHECKING:
    from .basebehavior import Behavior  # noqa: F401
    from ..tabs import Tab  # noqa: F401

__all__ = [
    "BehaviorMatcher",
    "BehaviorManager",
    "load_behavior_class",
    "create_default_behavior_man",
]

logger = logging.getLogger("autobrowser")


def load_behavior_class(handler: Dict[str, str]) -> Type["Behavior"]:
    """Dynamically loads the Behavior class based on the behavior configs handler filed

    :param handler: The dictionary containing the module and class information about
    the behavior to be loaded
    :return: The loaded behavior class
    """
    mod = handler.get("module")
    if not mod.startswith("autobrowser"):
        mod = f"autobrowser.behaviors.{mod}"
    behavior = getattr(
        import_module(mod), handler.get("class")
    )  # type: Type["Behavior"]
    return behavior


@attr.dataclass(slots=True)
class BehaviorMatcher(object):
    """Combines both the matching of URLs to their behaviors and creating the behaviors
    based on the supplied behavior config.

    The definition for the URL matching behavior, provided by urlcanon.rules.MatchRule,
    is expected to be defined in the "match" key of the behavior_config dictionary. See
    urlcanon.rules.MatchRule for more information.
    """

    behavior_config: Dict = attr.ib()
    behavior_class: Optional[Type["Behavior"]] = attr.ib(default=None)
    matcher: MatchRule = attr.ib(init=False)

    @matcher.default
    def matcher_default(self):
        return MatchRule(**self.behavior_config.get("match"))

    def create_behavior(
        self, tab: "Tab", **kwargs: Any
    ) -> "Behavior":
        """Create the Behavior associated with the rule.

        :param tab: The tab the rule is for
        :return: The instantiated Behavior
        """
        if self.behavior_class is None:
            self.behavior_class = load_behavior_class(
                self.behavior_config.get("handler")
            )
        return self.behavior_class(tab, self.behavior_config.get("init"), **kwargs)

    def applies(self, url: str) -> bool:
        return self.matcher.applies(url)


@attr.dataclass(slots=True)
class _BehaviorManager(object):
    """Manages matching URL to their corresponding behaviors."""

    matchers: List[BehaviorMatcher] = attr.ib()
    default_behavior_init: Tuple[Type["Behavior"], Dict] = attr.ib()

    def behavior_for_url_exact(
        self, url: str, tab: "Tab", **kwargs: Any
    ) -> Optional["Behavior"]:
        """Retrieve the behavior for the supplied URL exactly.

        If no behavior's URL matches then None is returned

        :param url: The url to receive the Behavior class for
        :param tab: The browser tab the behavior is to run in
        :return: The Behavior for the URL or None indicating
        no exact match
        """
        for rule in self.matchers:
            if rule.applies(url):
                return rule.create_behavior(tab, **kwargs)
        return None

    def behavior_for_url(
        self, url: str, tab: "Tab", **kwargs: Any
    ) -> "Behavior":
        """Retrieve the behavior for the supplied URL, if no behavior's
        url matches then a default behavior is returned.

        :param url: The url to receive the Behavior class for
        :param tab: The browser tab the behavior is to run in
        :return: The Behavior for the URL
        """
        matched_behavior = self.behavior_for_url_exact(url, tab, **kwargs)
        if matched_behavior is not None:
            logger.info(
                f"BehaviorManager[behavior_for_url]: Matched {url} to {matched_behavior}"
            )
            return matched_behavior
        clazz, init = self.default_behavior_init
        logger.info(
            f"BehaviorManager[behavior_for_url]: No exact behavior match for {url}, using autoscroll behavior"
        )
        return clazz(tab, init, **kwargs)


def create_default_behavior_man() -> "_BehaviorManager":
    """Create the default BehaviorManager, rules are loaded from the default config found in
    the directory containing this file."""
    yaml = YAML()
    with (Path(__file__).parent / "behaviors.yaml").open("r") as iin:
        config = yaml.load(iin)
    rules = []
    for conf in config["matching"]:
        rules.append(BehaviorMatcher(conf))
    default = config["default"]
    default_behavior = load_behavior_class(default["handler"])
    return _BehaviorManager(rules, (default_behavior, default["init"]))


BehaviorManager = create_default_behavior_man()
