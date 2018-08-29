# -*- coding: utf-8 -*-
from typing import Callable, Dict, List, Union, Type

from pyee import EventEmitter

__all__ = ["Helper"]


class Helper(object):
    @staticmethod
    def add_event_listener(
        emitter: EventEmitter, eventName: str, handler: Callable
    ) -> Dict[str, Union[str, Type[EventEmitter], Callable]]:
        """Add handler to the emitter and return emitter/handler."""
        emitter.on(eventName, handler)
        return {"emitter": emitter, "eventName": eventName, "handler": handler}

    @staticmethod
    def remove_event_listeners(
        listeners: List[Dict[str, Union[str, Type[EventEmitter], Callable]]]
    ) -> None:
        """Remove listeners from emitter."""
        for listener in listeners:
            emitter = listener["emitter"]
            eventName = listener["eventName"]
            handler = listener["handler"]
            emitter.remove_listener(eventName, handler)
        listeners.clear()
