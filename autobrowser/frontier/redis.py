from asyncio import AbstractEventLoop, gather as aio_gather, sleep as aio_sleep
from typing import Any, Awaitable, Dict, Iterable, List, Union
from ujson import dumps as ujson_dumps, loads as ujson_loads

from aioredis import Redis
from attr import dataclass as attr_dataclass, ib as attr_ib

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
    currently_crawling: Dict[str, Union[str, int]] = attr_ib(init=False, default=None)
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
        """Returns the next depth by adding one to the depth of the currently crawled URLs depth"""
        if self.currently_crawling is not None:
            return self.currently_crawling["depth"] + 1
        return -1

    async def q_len(self) -> int:
        """Returns an Awaitable that resolves to the length of the frontier's q"""
        return await self.redis.llen(self.keys.queue)

    async def exhausted(self) -> bool:
        """Returns a boolean that indicates if the frontier is exhausted or not"""
        qlen = await self.redis.llen(self.keys.queue)
        self.logger.info("exhausted", f"len(queue) = {qlen}")
        return qlen == 0

    async def is_seen(self, url: str) -> bool:
        """Returns an Awaitable that resolves with a boolean that indicates if the supplied URL has been seen or not"""
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
        """If currently_crawling url is set, remove it from pending set
        """
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

    async def add(self, url: str, depth: int) -> None:
        """Conditionally adds a URL to frontier.

        The addition condition is not seen and in scope.

        :param url: The URL to maybe add to the frontier
        :param depth: The depth the URL is to be crawled at
        """
        should_add = self.scope.in_scope(url)
        is_seen = await self.is_seen(url)
        if should_add and not is_seen:
            await aio_gather(
                self.redis.rpush(
                    self.keys.queue, ujson_dumps(dict(url=url, depth=depth))
                ),
                self.redis.sadd(self.keys.seen, url),
                loop=self.loop,
            )

    async def add_all(self, urls: Iterable[str]) -> None:
        """Conditionally adds URLs to frontier.

        The addition condition is not seen and in scope.

        :param urls: An iterable containing URLs to be added
        to the frontier
        """
        next_depth = self.next_depth()
        if next_depth > self.crawl_depth:
            return

        logged_method = "add_all"

        self.logger.info(
            logged_method,
            f"The next depth is {next_depth}. Max depth = {self.crawl_depth}",
        )

        seen_list: List[str] = []
        urls_to_q: List[str] = []

        self_logger_info = self.logger.info
        is_url_seen = self.is_seen
        is_url_in_scope = self.scope.in_scope
        seen_list_append = seen_list.append
        urls_to_q_append = urls_to_q.append

        for url in urls:
            is_seen = await is_url_seen(url)
            in_scope = is_url_in_scope(url)
            self_logger_info(
                logged_method,
                f'{{"url": "{url}", "seen": {is_seen}, "in_scope": {in_scope}, "depth": {next_depth}}}',
            )
            if in_scope and not is_seen:
                seen_list_append(url)
                urls_to_q_append(ujson_dumps(dict(url=url, depth=next_depth)))

        qlen = len(urls_to_q)
        self_logger_info(logged_method, f"adding {qlen} urls to the frontier")
        if qlen > 0:
            await aio_gather(
                self.redis.rpush(self.keys.queue, *urls_to_q),
                self.redis.sadd(self.keys.seen, *seen_list),
                loop=self.loop,
            )

    def __attrs_post_init__(self) -> None:
        self.scope = RedisScope(self.redis, self.keys)
        self.logger = create_autologger("frontier", "RedisFrontier")
