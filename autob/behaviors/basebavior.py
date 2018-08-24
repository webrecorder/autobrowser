# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from typing import Type

from ..tabs.basetab import BaseAutoTab

__all__ = ["Behavior"]


class Behavior(object, metaclass=ABCMeta):
    """Base page behavior class.

    A page behavior represents an action that is to be performed in the page and its frames.
    """

    def __init__(self, tab: Type[BaseAutoTab]) -> None:
        self.tab = tab
        self.paused = False
        self._controlled = False

    @property
    def controlled(self):
        return self._controlled

    @abstractmethod
    async def run(self):
        pass

    def __await__(self):
        return self.run().__await__()
