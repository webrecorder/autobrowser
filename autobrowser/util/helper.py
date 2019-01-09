import asyncio
from asyncio import AbstractEventLoop
from typing import Callable, Dict, List, Optional, Union

from pyee import EventEmitter

__all__ = ["Helper", "ListenerDict"]

ListenerDict = Dict[str, Union[str, EventEmitter, Callable]]


class Helper(object):
    """Utility class providing helpful utility functions"""

    @staticmethod
    def add_event_listener(
        emitter: EventEmitter, event_name: str, handler: Callable
    ) -> ListenerDict:
        """Registers an event listener (handler) on the emitter and returns
        a dictionary with keys emitter, eventName, and handler for ease of
        removal

        :param emitter: The EventEmitter to register the event handler on
        :param event_name: The event name the handler will be registered for
        :param handler: The event handler to be registered for event_name
        :return: Dictionary with keys emitter, eventName, and handler
        """
        emitter.on(event_name, handler)
        return dict(emitter=emitter, eventName=event_name, handler=handler)

    @staticmethod
    def remove_event_listeners(listeners: List[ListenerDict]) -> None:
        """Remove listeners from emitter

        :param listeners: List of dictionaries returned by add_event_listener
        """
        for listener in listeners:
            emitter = listener["emitter"]  # type: EventEmitter
            event_name = listener["eventName"]  # type: str
            handler = listener["handler"]  # type: Callable
            emitter.remove_listener(event_name, handler)
        listeners.clear()

    @staticmethod
    def ensure_loop(loop: Optional[AbstractEventLoop] = None) -> AbstractEventLoop:
        if loop is not None:
            return loop
        return asyncio.get_event_loop()
