from asyncio import AbstractEventLoop
from types import TracebackType
from typing import Any, Optional, TYPE_CHECKING, Type
from ujson import dumps as ujson_dumps

from aiohttp import AsyncResolver, ClientResponse, ClientSession, TCPConnector

from .helper import Helper

__all__ = [
    "HTTPGet",
    "HTTPPost",
    "HTTPRequestSession",
    "create_aio_http_client_session",
]

if TYPE_CHECKING:
    from aiohttp.client import _RequestContextManager


def create_aio_http_client_session(
    loop: Optional[AbstractEventLoop] = None
) -> ClientSession:
    if loop is None:
        loop = Helper.ensure_loop(loop)
    return ClientSession(
        connector=TCPConnector(resolver=AsyncResolver(loop=loop), loop=loop),
        json_serialize=ujson_dumps,
        loop=loop,
        trust_env=True,
    )


class HTTPRequestSession:
    """Async context manager wrapper around aiohttp.client.ClientSession"""

    __slots__ = ("_loop", "_session")

    def __init__(self, loop: Optional[AbstractEventLoop] = None) -> None:
        """Initialize a new HTTPRequestSession instance

        :param loop: The event loop to be used, defaults to aio.get_event_loop()
        """
        self._loop = Helper.ensure_loop(loop)
        self._session = create_aio_http_client_session(self._loop)

    async def __aenter__(self) -> ClientSession:
        return self._session

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self._session.close()

    def __str__(self) -> str:
        return "HTTPRequestSession"

    def __repr__(self) -> str:
        return self.__str__()


class HTTPGet:
    """Utility async context manager for making HTTP GET requests"""

    __slots__ = ("_kwargs", "_response", "_session", "_url")

    def __init__(
        self, url: str, loop: Optional[AbstractEventLoop] = None, **kwargs: Any
    ) -> None:
        """Initialize a new HTTP request async context manager

        :param url: The URL for the request
        :param loop: The event loop to be used, defaults to aio.get_event_loop()
        :param kwargs: Optional keyword arguments to be supplied to the request function
        """
        self._url: str = url
        self._kwargs: Any = kwargs
        self._session: ClientSession = create_aio_http_client_session(
            Helper.ensure_loop(loop)
        )
        self._response: "_RequestContextManager" = None

    async def __aenter__(self) -> ClientResponse:
        self._response = self._session.get(self._url, **self._kwargs)
        return await self._response.__aenter__()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self._response.__aexit__(exc_type, exc_val, exc_tb)
        await self._session.close()

    def __str__(self) -> str:
        return f"HTTPGet<url={self._url}, {self._kwargs}>"

    def __repr__(self) -> str:
        return self.__str__()


class HTTPPost:
    """Utility async context manager for making HTTP POST requests"""

    __slots__ = ("_kwargs", "_loop", "_response", "_session", "_url")

    def __init__(
        self, url: str, loop: Optional[AbstractEventLoop] = None, **kwargs: Any
    ) -> None:
        """Initialize a new HTTP request async context manager

        :param url: The URL for the request
        :param loop: The event loop to be used, defaults to aio.get_event_loop()
        :param kwargs: Optional keyword arguments to be supplied to the request function
        """
        self._url: str = url
        self._loop: AbstractEventLoop = Helper.ensure_loop(loop)
        self._kwargs: Any = kwargs
        self._session: ClientSession = create_aio_http_client_session(self._loop)
        self._response: "_RequestContextManager" = None

    async def __aenter__(self) -> ClientResponse:
        self._response = self._session.post(self._url, **self._kwargs)
        return await self._response.__aenter__()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self._response.__aexit__(exc_type, exc_val, exc_tb)
        await self._session.close()

    def __str__(self) -> str:
        return f"HTTPPost<url={self._url}, {self._kwargs}>"

    def __repr__(self) -> str:
        return self.__str__()
