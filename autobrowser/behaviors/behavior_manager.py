from typing import Type, List, TYPE_CHECKING

from urlcanon.rules import MatchRule

from .scroll import AutoScrollBehavior
from .timelines_feeds import TwitterTimelineBehavior, FBNewsFeedBehavior, FBUserFeedBehavior

if TYPE_CHECKING:
    from .basebehavior import Behavior

__all__ = ["URLMatcher", "BehaviorManager"]


class URLMatcher(MatchRule):
    def __init__(self, behavior_class: Type["Behavior"], **kwargs) -> None:
        super().__init__(**kwargs)
        self.behavior_class: Type["Behavior"] = behavior_class


class _BehaviorManager(object):
    def __init__(self):
        self.rules: List[URLMatcher] = [
            URLMatcher(
                TwitterTimelineBehavior, regex="^https://(www.)?twitter.com/[^/]+$"
            ),
            URLMatcher(
                FBNewsFeedBehavior, regex="^https://(www.)?facebook.com(/[?]sk=nf)?$"
            ),
            URLMatcher(
                FBUserFeedBehavior, regex="^https://(www.)?facebook.com/[^/]+$"
            ),
        ]

    def behavior_for_url(self, url: str) -> Type["Behavior"]:
        """Retrieve the behavior class for the supplied URL

        :param url: The url to receive the Behavior class for
        :return: The Behavior class for the rule
        """
        for rule in self.rules:
            if rule.applies(url):
                return rule.behavior_class
        return AutoScrollBehavior


BehaviorManager = _BehaviorManager()
