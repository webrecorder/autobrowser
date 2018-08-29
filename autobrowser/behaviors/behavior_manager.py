# asb = AutoScrollBehavior(tab=tab)
#         if asb.has_resources:
#             await asb.load_resources()
#         tab.add_behavior(asb)
from typing import Type

from .scroll import AutoScrollBehavior
from .basebehavior import Behavior


class BehaviorManager(object):
    @staticmethod
    def behavior_for_url(url: str) -> Type[Behavior]:
        return AutoScrollBehavior


behavior_class = BehaviorManager.behavior_for_url('https')

instance: Behavior = behavior_class()
