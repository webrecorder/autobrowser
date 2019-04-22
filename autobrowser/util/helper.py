from asyncio import (
    AbstractEventLoop,
    CancelledError,
    Future,
    Task,
    TimeoutError,
    get_event_loop,
    sleep,
)
from functools import partial
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from aiohttp import AsyncResolver, ClientSession, TCPConnector
from async_timeout import timeout as aio_timeout
from pyee2 import EventEmitter
from simplechrome.helper import Helper as SC_Helper
from ujson import dumps

__all__ = ["Helper", "ListenerDict"]

ListenerDict = Dict[str, Union[str, EventEmitter, Callable]]


class Helper(SC_Helper):
    """Utility class providing helpful utility functions that extends the helper class by simplechrome"""

    @staticmethod
    def event_loop() -> AbstractEventLoop:
        """Returns the event used by the automation

        :return: The event loop instance used by the automation
        """
        return get_event_loop()

    @staticmethod
    def ensure_loop(loop: Optional[AbstractEventLoop] = None) -> AbstractEventLoop:
        """If the supplied loop is none the event loop returns by asyncio.get_event_loop() is returned
        otherwise the supplied loop instance

        :param loop: A reference to the automation event loop that could be None
        :return: The event loop used by the automation
        """
        if loop is not None:
            return loop
        return get_event_loop()

    @staticmethod
    def create_aio_http_client_session(
        loop: Optional[AbstractEventLoop] = None
    ) -> ClientSession:
        """Creates and returns a new aiohttp.ClientSession.
        The returned aiohttp.ClientSession is configured to use ujson for JSON serialization
        and aiohttp.AsyncResolver as its dns resolver

        :param loop: Optional reference to the automation's event loop
        :return: The newly created aiohttp.ClientSession
        """
        eloop = Helper.ensure_loop(loop)
        return ClientSession(
            connector=TCPConnector(resolver=AsyncResolver(loop=eloop), loop=eloop),
            json_serialize=partial(dumps, ensure_ascii=False),
            loop=eloop,
        )

    @staticmethod
    def one_tick_sleep() -> Awaitable[None]:
        """Returns an awaitable to resolves on the next event loop tick"""
        return sleep(0)

    @staticmethod
    async def timed_future_completion(
        task_or_future: Union[Task, Future],
        timeout: Union[int, float] = 10,
        cancel: bool = False,
        loop: Optional[AbstractEventLoop] = None,
    ) -> None:
        """Waits for the supplied task/future to resolve until the timeout time has been reached.
        If cancel is true the supplied task/future is cancelled then awaited.

        :param task_or_future: The task/future to be awaited
        :param timeout: The maximum amount of time the wait will be. Defaults to 10 seconds
        :param cancel: Should the task/future be canceled before awaiting completing. Defaults to False
        :param loop: Optional reference to the automation's event loop.
        """
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

    @staticmethod
    async def no_raise_await(awaitable: Awaitable[Any]) -> None:
        """Awaits the completion of the supplied await swallowing any exceptions it raises

        :param awaitable: The awaitable to be awaited
        """
        try:
            await awaitable
        except Exception:
            pass

    @staticmethod
    def logged_json_string(**kwargs: Any) -> str:
        """A simple utility for creating valid json used to log additional info"""
        return f"{kwargs}"
