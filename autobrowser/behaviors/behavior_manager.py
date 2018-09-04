from typing import Type, List, TYPE_CHECKING

from urlcanon.rules import MatchRule
import attr
from .scroll import AutoScrollBehavior
from .twitterTimeline import TwitterTimelineBehavior

if TYPE_CHECKING:
    from .basebehavior import Behavior


class URLMatcher(MatchRule):

    def __init__(self, behavior_class: Type["Behavior"], **kwargs) -> None:
        super().__init__(**kwargs)
        self.behavior_class: Type["Behavior"] = behavior_class


class _BehaviorManager(object):
    def __init__(self):
        self.rules: List[URLMatcher] = [
            URLMatcher(
                TwitterTimelineBehavior, regex="^https://(www.)?twitter.com/[^/]+$"
            )
        ]

    def behavior_for_url(self, url: str) -> Type["Behavior"]:
        for rule in self.rules:
            if rule.applies(url):
                return rule.behavior_class
        return AutoScrollBehavior


BehaviorManager = _BehaviorManager()
