# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from ..tabs.basetab import BaseAutoTab


__all__ = ["Behavior"]


class Behavior(object, metaclass=ABCMeta):
    """Base page behavior class.

    A page behavior represents an action that is to be performed in the page and its frames.
    """

    def __init__(self, tab: Type["BaseAutoTab"]) -> None:
        self.tab: "BaseAutoTab" = tab
        self.paused: bool = False
        self._controlled: bool = False
        self._has_resource: bool = False

    @property
    def has_resources(self) -> bool:
        return self._has_resource

    @property
    def controlled(self) -> bool:
        return self._controlled

    @abstractmethod
    async def run(self):
        pass

    @abstractmethod
    async def load_resources(self):
        pass

    def __await__(self):
        return self.run().__await__()
