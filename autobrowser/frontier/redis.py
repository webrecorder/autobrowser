import asyncio
from asyncio import sleep as aio_sleep, gather as aio_gather
import logging
from ujson import dumps as ujson_dumps, loads as ujson_loads
from asyncio import AbstractEventLoop
from typing import Any, Awaitable, ClassVar, Dict, List, Iterable, Union

import attr
from aioredis import Redis

from autobrowser.automation import RedisKeys
from autobrowser.scope import RedisScope


__all__ = ["RedisFrontier"]

logger = logging.getLogger("autobrowser")

log_info = logger.info


@attr.dataclass(slots=True)
class RedisFrontier(object):
    redis: Redis = attr.ib(repr=False)
    keys: RedisKeys = attr.ib()
    loop: AbstractEventLoop = attr.ib(factory=asyncio.get_event_loop)
    scope: RedisScope = attr.ib(init=False)
    crawl_depth: int = attr.ib(init=False, default=-1)
    currently_crawling: Dict[str, Union[str, int]] = attr.ib(init=False, default=None)

    CRAWL_DEPTH_FIELD: ClassVar[str] = "crawl_depth"

    @scope.default
    def _init_scope(self) -> RedisScope:
        return RedisScope(self.redis, self.keys)

    async def wait_for_populated_q(self, wait_time: Union[int, float] = 60) -> None:
        """Waits for the q to become populated by polling exhausted at wait_time intervals.

        :param wait_time: The interval time in seconds for polling exhausted. Defaults to 60
        """
        log_info(
            f"RedisFrontier[wait_for_populated_q]: starting wait loop, checking every {wait_time} seconds"
        )
        is_frontier_exhausted = self.exhausted
        frontier_exhausted = await is_frontier_exhausted()
        while frontier_exhausted:
            log_info(
                f"RedisFrontier[wait_for_populated_q]: q still empty, waiting another {wait_time} seconds"
            )
            await aio_sleep(wait_time, loop=self.loop)
            frontier_exhausted = await is_frontier_exhausted()
        q_len = await self.q_len()
        logger.info(
            f"RedisFrontier[wait_for_populated_q]: q populated with {q_len} URLs"
        )

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
        log_info(f"RedisFrontier[exhausted]: len(queue) = {qlen}")
        return qlen == 0

    async def is_seen(self, url: str) -> bool:
        """Returns an Awaitable that resolves with a boolean that indicates if the supplied URL has been seen or not"""
        return await self.redis.sismember(self.keys.seen, url) == 1

    def add_to_pending(self, url: str) -> Awaitable[Any]:
        """Add the supplied URL to the pending set

        :param url: The URL to add to the pending set
        """
        log_info(f"RedisFrontier[add_to_pending]: Adding {url} to the pending set")
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
        log_info(f"RedisFrontier[next_url]: the next URL is {self.currently_crawling}")
        await self.add_to_pending(self.currently_crawling["url"])
        return self.currently_crawling["url"]

    async def remove_current_from_pending(self) -> None:
        """If currently_crawling url is set, remove it from pending set
        """
        if self.currently_crawling is not None:
            log_info(
                f"RedisFrontier[next_url]: removing the previous URL {self.currently_crawling} from the pending set"
            )
            curl: str = self.currently_crawling["url"]
            await self.remove_from_pending(curl)
            self.currently_crawling = None

    async def init(self) -> None:
        """Initialize the frontier"""
        self.crawl_depth = int(
            await self.redis.hget(self.keys.info, self.CRAWL_DEPTH_FIELD) or 0
        )
        log_info(f"RedisFrontier[init]: crawl depth = {self.crawl_depth}")
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
        logger.info(
            f"RedisFrontier[add_all]: The next depth is {next_depth}. Max depth = {self.crawl_depth}"
        )
        if next_depth > self.crawl_depth:
            return
        seen_list: List[str] = []
        urls_to_q: List[str] = []

        # https://wiki.python.org/moin/PythonSpeed/PerformanceTips: Avoiding dots...
        is_url_seen = self.is_seen
        is_url_in_scope = self.scope.in_scope
        add_to_seen = seen_list.append
        add_to_q = urls_to_q.append

        for url in urls:
            is_seen = await is_url_seen(url)
            in_scope = is_url_in_scope(url)
            log_info(
                f'RedisFrontier[add_all]: {{"url": "{url}", "seen": '
                f'{is_seen}, "in_scope": {in_scope}, "depth": {next_depth}}}'
            )
            if in_scope and not is_seen:
                add_to_seen(url)
                add_to_q(ujson_dumps(dict(url=url, depth=next_depth)))
        qlen = len(urls_to_q)
        log_info(f"RedisFrontier[add_all]: adding {qlen} urls to the frontier")
        if qlen > 0:
            await aio_gather(
                self.redis.rpush(self.keys.queue, *urls_to_q),
                self.redis.sadd(self.keys.seen, *seen_list),
                loop=self.loop,
            )
