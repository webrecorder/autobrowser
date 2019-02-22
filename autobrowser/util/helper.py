from asyncio import (
    AbstractEventLoop,
    CancelledError,
    Future,
    Task,
    TimeoutError,
    get_event_loop as aio_get_event_loop,
    sleep as aio_sleep,
)
from typing import Awaitable, Callable, Dict, List, Optional, Union

from aiohttp import AsyncResolver, ClientSession, TCPConnector
from async_timeout import timeout as aio_timeout
from pyee2 import EventEmitter
from ujson import dumps as ujson_dumps
from functools import partial

__all__ = ["Helper", "ListenerDict"]

ListenerDict = Dict[str, Union[str, EventEmitter, Callable]]


class Helper:
    """Utility class providing helpful utility functions"""

    __slots__ = ()

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
            emitter: EventEmitter = listener["emitter"]
            event_name: str = listener["eventName"]
            handler: Callable = listener["handler"]
            emitter.remove_listener(event_name, handler)
        listeners.clear()

    @staticmethod
    def ensure_loop(loop: Optional[AbstractEventLoop] = None) -> AbstractEventLoop:
        if loop is not None:
            return loop
        return aio_get_event_loop()

    @staticmethod
    def create_aio_http_client_session(
        loop: Optional[AbstractEventLoop] = None
    ) -> ClientSession:
        eloop = Helper.ensure_loop(loop)
        return ClientSession(
            connector=TCPConnector(resolver=AsyncResolver(loop=eloop), loop=eloop),
            json_serialize=partial(ujson_dumps, ensure_ascii=False),
            loop=eloop,
        )

    @staticmethod
    def one_tick_sleep() -> Awaitable[None]:
        """Returns an awaitable to resolves on the next event loop tick"""
        return aio_sleep(0)

    @staticmethod
    async def timed_future_completion(
        task_or_future: Union[Task, Future],
        timeout: Union[int, float] = 10,
        cancel: bool = False,
        loop: Optional[AbstractEventLoop] = None,
    ) -> None:
        _loop = Helper.ensure_loop(loop)
        if cancel and not task_or_future.done():
            task_or_future.cancel()
        try:
            async with aio_timeout(timeout, loop=_loop):
                await task_or_future
        except (CancelledError, TimeoutError):
            pass
        except Exception:
            raise
