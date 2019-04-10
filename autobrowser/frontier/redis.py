from asyncio import AbstractEventLoop, sleep as aio_sleep
from typing import Any, Awaitable, Dict, Iterable, Optional, Union

from aioredis import Redis
from attr import dataclass as attr_dataclass, ib as attr_ib
from ujson import dumps as ujson_dumps, loads as ujson_loads

from autobrowser.automation import RedisKeys
from autobrowser.scope import RedisScope
from autobrowser.util import AutoLogger, Helper, create_autologger

__all__ = ["RedisFrontier"]

CRAWL_DEPTH_FIELD: str = "crawl_depth"


@attr_dataclass(slots=True)
class RedisFrontier:
    redis: Redis = attr_ib(repr=False)
    keys: RedisKeys = attr_ib()
    loop: AbstractEventLoop = attr_ib(
        default=None, converter=Helper.ensure_loop, repr=False
    )
    scope: RedisScope = attr_ib(init=False, default=None)
    crawl_depth: int = attr_ib(init=False, default=-1)
    currently_crawling: Optional[Dict[str, Union[str, int]]] = attr_ib(
        init=False, default=None
    )
    logger: AutoLogger = attr_ib(default=None, init=False, repr=False)

    async def wait_for_populated_q(self, wait_time: Union[int, float] = 60) -> None:
        """Waits for the q to become populated by polling exhausted at wait_time intervals.

        :param wait_time: The interval time in seconds for polling exhausted. Defaults to 60
        """
        logged_method = f"wait_for_populated_q(wait_time={wait_time})"
        self.logger.info(logged_method, "starting wait loop")

        frontier_exhausted = await self.exhausted()
        eloop = self.loop
        is_frontier_exhausted = self.exhausted
        self_logger_info = self.logger.info

        while frontier_exhausted:
            self_logger_info(logged_method, "q still not populated waiting")
            await aio_sleep(wait_time, loop=eloop)
            frontier_exhausted = await is_frontier_exhausted()

        q_len = await self.q_len()
        self.logger.info(logged_method, f"q populated with {q_len} URLs")

    def next_depth(self) -> int:
        """Returns the next depth by adding one to the depth of the currently crawled URLs depth

        :return: The next depth
        """
        if self.currently_crawling is not None:
            return self.currently_crawling["depth"] + 1
        return -1

    async def q_len(self) -> int:
        """Returns an Awaitable that resolves to the length of the frontier's q

        :return: The length of the queue
        """
        return await self.redis.llen(self.keys.queue)

    async def exhausted(self) -> bool:
        """Returns a boolean that indicates if the frontier is exhausted or not

        :return: T/F indicating if the frontier is exhausted
        """
        qlen = await self.redis.llen(self.keys.queue)
        self.logger.info("exhausted", f"len(queue) = {qlen}")
        return qlen == 0

    async def is_seen(self, url: str) -> bool:
        """Returns an Awaitable that resolves with a boolean that indicates if
        the supplied URL has been seen or not

        :return: T/F indicating if the supplied URL is seen
        """
        return await self.redis.sismember(self.keys.seen, url) == 1

    def add_to_pending(self, url: str) -> Awaitable[Any]:
        """Add the supplied URL to the pending set

        :param url: The URL to add to the pending set
        """
        self.logger.info("add_to_pending", f"Adding {url} to the pending set")
        return self.redis.sadd(self.keys.pending, url)

    def remove_from_pending(self, url: str) -> Awaitable[Any]:
        """Remove the supplied URL from the pending set

        :param url: The URL to be removed from the pending set
        """
        return self.redis.srem(self.keys.pending, url)

    async def _pop_url(self) -> Dict[str, Union[str, int]]:
        """Pops (removes) the next URL to be crawled from
        the queue and returns it

        :return: The next URL to be crawled
        """
        udict_str = await self.redis.lpop(self.keys.queue)
        return ujson_loads(udict_str)

    async def next_url(self) -> str:
        """Retrieve the next URL to be crawled from the frontier and updates the pending set

        :return: The next URL to be crawled
        """
        self.currently_crawling = await self._pop_url()
        self.logger.info("next_url", f"the next URL is {self.currently_crawling}")
        await self.add_to_pending(self.currently_crawling["url"])
        return self.currently_crawling["url"]

    async def remove_current_from_pending(self) -> None:
        """If currently_crawling url is set, remove it from pending set"""
        if self.currently_crawling is not None:
            self.logger.info(
                "next_url",
                f"removing the previous URL {self.currently_crawling} from the pending set",
            )
            curl: str = self.currently_crawling["url"]
            await self.remove_from_pending(curl)
            self.currently_crawling = None

    async def init(self) -> None:
        """Initialize the frontier"""
        self.crawl_depth = int(
            await self.redis.hget(self.keys.info, CRAWL_DEPTH_FIELD) or 0
        )
        self.logger.info("init", f"crawl depth = {self.crawl_depth}")
        await self.scope.init()

    async def add(self, url: str, depth: int) -> bool:
        """Conditionally adds a URL to frontier.

        The addition condition is not seen and in scope.

        :param url: The URL to maybe add to the frontier
        :param depth: The depth the URL is to be crawled at
        :return: T/F indicating if the URL @ depth was added to the frontier
        """
        logged_method = "add"
        url_info = {"url": url, "depth": depth}

        in_scope = self.scope.in_scope(url)
        if not in_scope:
            self.logger.info(
                logged_method,
                f"Not adding URL to the frontier, not in scope - {url_info}",
            )
            return False

        was_added = await self.redis.sadd(self.keys.seen, url)
        if was_added == 0:
            self.logger.info(
                logged_method, f"Not adding URL to the frontier, seen - {url_info}"
            )
            return False

        self.logger.info(logged_method, f"Adding URL to the frontier - {url_info}")
        await self.redis.rpush(self.keys.queue, ujson_dumps(url_info))
        return True

    async def add_all(self, urls: Iterable[str]) -> bool:
        """Conditionally adds URLs to frontier.

        The addition condition is not seen and in scope.

        :param urls: An iterable containing URLs to be added
        to the frontier
        :return: T/F indicating if any of the URLs @ next depth were added to the frontier
        """
        logged_method = "add_all"
        next_depth = self.next_depth()
        if next_depth > self.crawl_depth:
            self.logger.info(
                logged_method,
                f"Not adding any URLs, maximum crawl depth exceeded. Max depth = {self.crawl_depth}",
            )
            return False

        self.logger.info(
            logged_method,
            f"The next depth is {next_depth}. Max depth = {self.crawl_depth}",
        )

        add_to_frontier = self.add
        num_added = 0

        for url in urls:
            was_added = await add_to_frontier(url, next_depth)
            if was_added:
                num_added += 1

        if num_added > 0:
            self.logger.info(logged_method, f"Added {num_added} urls to the frontier")
            return True

        self.logger.info(logged_method, f"No URLs added to the frontier")
        return False

    def __attrs_post_init__(self) -> None:
        self.scope = RedisScope(self.redis, self.keys)
        self.logger = create_autologger("frontier", "RedisFrontier")
