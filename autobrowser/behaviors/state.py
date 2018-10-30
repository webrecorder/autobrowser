from typing import Any

import attr
from enum import Enum, auto

__all__ = ["Action", "BehaviorState"]


class Action(Enum):
    BEGIN = auto()
    DONE = auto()
    WAIT = auto()
    CONTINUE = auto()
    SWITCH_TO_FRAME = auto()


@attr.dataclass(slots=True)
class BehaviorState(object):
    actionValue: Any = attr.ib(default=None, init=False)
    action: Action = attr.ib(default=Action.BEGIN, init=False)

    def transition_done(self) -> None:
        self.action = Action.DONE
        self.actionValue = None

    @property
    def done(self) -> bool:
        return self.action is Action.DONE

    @property
    def wait(self) -> bool:
        return self.action is Action.WAIT

    @property
    def contiueable(self) -> bool:
        return self.action is Action.CONTINUE

    @property
    def switch_to_frame(self) -> bool:
        return self.action is Action.SWITCH_TO_FRAME
