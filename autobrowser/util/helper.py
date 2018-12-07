# -*- coding: utf-8 -*-
import asyncio
from asyncio import AbstractEventLoop
from typing import Callable, Dict, List, Union, Optional

from pyee import EventEmitter

__all__ = ["Helper", "ListenerDict"]

ListenerDict = Dict[str, Union[str, EventEmitter, Callable]]


class Helper(object):
    """Utility class providing functions that perform"""

    @staticmethod
    def add_event_listener(
        emitter: EventEmitter, event_name: str, handler: Callable
    ) -> ListenerDict:
        """Add handler to the emitter and return emitter/handler."""
        emitter.on(event_name, handler)
        return {"emitter": emitter, "eventName": event_name, "handler": handler}

    @staticmethod
    def remove_event_listeners(listeners: List[ListenerDict]) -> None:
        """Remove listeners from emitter."""
        for listener in listeners:
            emitter = listener["emitter"]  # type: EventEmitter
            event_name = listener["eventName"]
            handler = listener["handler"]
            emitter.remove_listener(event_name, handler)
        listeners.clear()

    @staticmethod
    def ensure_loop(loop: Optional[AbstractEventLoop] = None) -> AbstractEventLoop:
        if loop is not None:
            return loop
        return asyncio.get_event_loop()
