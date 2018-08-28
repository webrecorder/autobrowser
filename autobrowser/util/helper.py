# -*- coding: utf-8 -*-
from typing import Dict, Any, List, Callable

from pyee import EventEmitter

__all__ = ["Helper"]


class Helper(object):
    @staticmethod
    def addEventListener(
        emitter: EventEmitter, eventName: str, handler: Callable
    ) -> Dict[str, Any]:
        """Add handler to the emitter and return emitter/handler."""
        emitter.on(eventName, handler)
        return {"emitter": emitter, "eventName": eventName, "handler": handler}

    @staticmethod
    def removeEventListeners(listeners: List[dict]) -> None:
        """Remove listeners from emitter."""
        for listener in listeners:
            emitter = listener["emitter"]
            eventName = listener["eventName"]
            handler = listener["handler"]
            emitter.remove_listener(eventName, handler)
        listeners.clear()
