# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

import aiofiles
import attr

if TYPE_CHECKING:
    from ..tabs.basetab import BaseAutoTab  # noqa: F401


__all__ = ["Behavior", "JSBasedBehavior"]


@attr.dataclass
class Behavior(object, metaclass=ABCMeta):
    """A behavior represents an action that is to be performed in the page (tab).

    This class defines the expected interface for all behaviors.
    Each behavior has an associated tab and configuration. If a behaviors configuration is not supplied
    then it is an empty dictionary, allowing subclasses to fill in information as necessary.
    """

    tab: "BaseAutoTab" = attr.ib()
    conf: Dict = attr.ib(factory=dict)
    contextId: Optional[int] = attr.ib(default=None)
    _has_resource: bool = attr.ib(default=False, init=False)
    _done: bool = attr.ib(default=False, init=False)
    _paused: bool = attr.ib(default=False, init=False)

    @property
    def done(self) -> bool:
        """Is the behavior done"""
        return self._done

    @property
    def paused(self) -> bool:
        """Is the behavior paused.

        A behavior in the paused state indicates that it has yet to reach its know completion point,
        but is waiting for some condition to occur before resuming.
        """
        return self._paused

    @property
    def has_resources(self) -> bool:
        """Does the behavior require resources to be loaded"""
        return self._has_resource

    async def load_resources(self):
        """Load the resources required by a behavior.

        Behaviors that require resources, typically JS, are expected to subclass JSBasedBehavior.
        """
        pass

    @abstractmethod
    async def run(self) -> bool:
        """Start the behaviors action"""
        pass

    def __await__(self):
        return self.run().__await__()


@attr.dataclass
class JSBasedBehavior(Behavior, metaclass=ABCMeta):
    """Specialized subclass of Behavior that require JavaScript to operate.

    The name of the JavaScript file a subclassing behavior requires is expected to
    be contained in the conf property under the 'resource' key. If the key 'pkg_resource'
    is false then the value of the 'resource' key is expected to be a full path to the file.
    """

    _did_init: bool = attr.ib(default=False, init=False)
    _resource: str = attr.ib(default="", init=False)
    _has_resource: bool = attr.ib(default=True, init=False)

    async def load_resources(self) -> None:
        resource = self.conf.get("resource")
        if self.conf.get("pkg_resource", True):
            resource = str(Path(__file__).parent / "behaviorjs" / resource)
        async with aiofiles.open(resource, "r") as iin:
            self._resource = await iin.read()
