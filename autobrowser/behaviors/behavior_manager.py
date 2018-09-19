# -*- coding: utf-8 -*-
from importlib import import_module
from pathlib import Path
from typing import Dict, List, Optional, Type, TYPE_CHECKING

import attr
from ruamel.yaml import YAML
from urlcanon.rules import MatchRule

from .scroll import AutoScrollBehavior

if TYPE_CHECKING:
    from .basebehavior import Behavior  # noqa: F401
    from ..tabs import BaseAutoTab  # noqa: F401

__all__ = ["URLMatcher", "BehaviorManager"]


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


@attr.s(auto_attribs=True)
class URLMatcher(MatchRule):
    """"""

    behavior_config: Dict = attr.ib()
    behavior_class: Optional[Type["Behavior"]] = attr.ib(default=None)

    def get_behavior(self, tab: "BaseAutoTab") -> "Behavior":
        if self.behavior_class is None:
            self.behavior_class = load_behavior_class(
                self.behavior_config.get("handler")
            )
        return self.behavior_class(tab, self.behavior_config.get("init"))

    def __attrs_post_init__(self) -> None:
        """Since we are subclassing MatchRule we must do the super init call here"""
        super().__init__(**self.behavior_config.get("match"))


@attr.s(auto_attribs=True, slots=True)
class _BehaviorManager(object):
    """dsa"""
    rules: List[URLMatcher] = attr.ib()

    def behavior_for_url(self, url: str, tab: "BaseAutoTab") -> "Behavior":
        """Retrieve the behavior class for the supplied URL

        :param url: The url to receive the Behavior class for
        :param tab: The browser tab the behavior is to run in
        :return: The Behavior class for the rule
        """
        for rule in self.rules:
            if rule.applies(url):
                return rule.get_behavior(tab)
        return AutoScrollBehavior(tab)

    @staticmethod
    def init() -> "_BehaviorManager":
        yaml = YAML()
        with (Path(__file__).parent / "behaviors.yaml").open("r") as iin:
            config = yaml.load(iin)
        rules = []
        for conf in config:
            rules.append(URLMatcher(conf))
        return _BehaviorManager(rules)


BehaviorManager = _BehaviorManager.init()
