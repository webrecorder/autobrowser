# -*- coding: utf-8 -*-
from importlib import import_module
from pathlib import Path
from typing import Dict, List, Optional, Type, TYPE_CHECKING, Tuple

import attr
from ruamel.yaml import YAML
from urlcanon.rules import MatchRule

if TYPE_CHECKING:
    from .basebehavior import Behavior  # noqa: F401
    from ..tabs import BaseAutoTab  # noqa: F401

__all__ = [
    "BehaviorMatcher",
    "BehaviorManager",
    "load_behavior_class",
    "create_default_behavior_man",
]


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


@attr.dataclass
class BehaviorMatcher(MatchRule):
    """Combines both the matching of URLs to their behaviors and creating the behaviors
    based on the supplied behavior config.

    The definition for the URL matching behavior, provided by urlcanon.rules.MatchRule,
    is expected to be defined in the "match" key of the behavior_config dictionary. See
    urlcanon.rules.MatchRule for more information.
    """

    behavior_config: Dict = attr.ib()
    behavior_class: Optional[Type["Behavior"]] = attr.ib(default=None)

    def create_behavior(self, tab: "BaseAutoTab") -> "Behavior":
        """Create the Behavior associated with the rule.

        :param tab: The tab the rule is for
        :return: The instantiated Behavior
        """
        if self.behavior_class is None:
            self.behavior_class = load_behavior_class(
                self.behavior_config.get("handler")
            )
        return self.behavior_class(tab, self.behavior_config.get("init"))

    def __attrs_post_init__(self) -> None:
        """Since we are subclassing MatchRule we must do the super init call here"""
        super().__init__(**self.behavior_config.get("match"))


@attr.dataclass(slots=True)
class _BehaviorManager(object):
    """Manages matching URL to their corresponding behaviors."""

    rules: List[BehaviorMatcher] = attr.ib()
    default_behavior_init: Tuple[Type["Behavior"], Dict] = attr.ib()

    def behavior_for_url(self, url: str, tab: "BaseAutoTab") -> "Behavior":
        """Retrieve the behavior for the supplied URL

        :param url: The url to receive the Behavior class for
        :param tab: The browser tab the behavior is to run in
        :return: The Behavior for the URL
        """
        for rule in self.rules:
            if rule.applies(url):
                return rule.create_behavior(tab)
        clazz, init = self.default_behavior_init
        return clazz(tab, init)


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
