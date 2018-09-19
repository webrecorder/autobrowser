# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Dict

import aiofiles
import attr

if TYPE_CHECKING:
    from ..tabs.basetab import BaseAutoTab  # noqa: F401


__all__ = ["Behavior", "JSBasedBehavior"]


@attr.s(auto_attribs=True)
class Behavior(object, metaclass=ABCMeta):
    """Base behavior class.

    A behavior represents an action that is to be performed in the page and its frames.
    """

    tab: "BaseAutoTab" = attr.ib()
    conf: Dict = attr.ib(factory=dict)
    paused: bool = attr.ib(default=False, init=False)
    _has_resource: bool = attr.ib(default=False, init=False)
    _done: bool = attr.ib(default=False, init=False)

    @property
    def done(self) -> bool:
        return self._done

    @property
    def has_resources(self) -> bool:
        return self._has_resource

    async def load_resources(self):
        pass

    @abstractmethod
    async def run(self):
        pass

    def __await__(self):
        return self.run().__await__()


@attr.s(auto_attribs=True)
class JSBasedBehavior(Behavior, metaclass=ABCMeta):
    _did_init: bool = attr.ib(default=False, init=False)
    _init_inject: str = attr.ib(default="", init=False)
    _has_resource: bool = attr.ib(default=True, init=False)

    async def load_resources(self) -> None:
        resource = self.conf.get("resource")
        if self.conf.get("pkg_resource", True):
            resource = str(Path(__file__).parent / 'behaviorjs' / resource)
        async with aiofiles.open(resource, "r") as iin:
            self._init_inject = await iin.read()
