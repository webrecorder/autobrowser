# -*- coding: utf-8 -*-
from typing import Callable, Dict, List, Union

from pyee import EventEmitter

__all__ = ["Helper"]


class Helper(object):
    """Utility class providing functions that perform"""

    @staticmethod
    def add_event_listener(
        emitter: EventEmitter, event_name: str, handler: Callable
    ) -> Dict[str, Union[str, EventEmitter, Callable]]:
        """Add handler to the emitter and return emitter/handler."""
        emitter.on(event_name, handler)
        return {"emitter": emitter, "eventName": event_name, "handler": handler}

    @staticmethod
    def remove_event_listeners(
        listeners: List[Dict[str, Union[str, EventEmitter, Callable]]]
    ) -> None:
        """Remove listeners from emitter."""
        for listener in listeners:
            emitter = listener["emitter"]  # type: EventEmitter
            event_name = listener["eventName"]
            handler = listener["handler"]
            emitter.remove_listener(event_name, handler)
        listeners.clear()
