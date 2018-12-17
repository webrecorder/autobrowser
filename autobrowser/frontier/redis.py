import asyncio
import logging
import ujson
from asyncio import AbstractEventLoop
from typing import List, Awaitable, ClassVar, Dict, Union, Iterable

import attr
from aioredis import Redis

from autobrowser.scope import RedisScope

__all__ = ["RedisFrontier"]

logger = logging.getLogger("autobrowser")


def to_redis_key(aid: str) -> str:
    return f"a:{aid}"


@attr.dataclass(slots=True)
class RedisFrontier(object):
    redis: Redis = attr.ib(repr=False)
    autoid: str = attr.ib(converter=to_redis_key)
    loop: AbstractEventLoop = attr.ib(factory=asyncio.get_event_loop)
    scope: RedisScope = attr.ib(init=False, default=None)
    info_key: str = attr.ib(init=False, default=None)
    q_key: str = attr.ib(init=False, default=None)
    pending_key: str = attr.ib(init=False, default=None)
    seen_key: str = attr.ib(init=False, default=None)
    crawl_depth: int = attr.ib(init=False, default=-1)
    currently_crawling: Dict[str, Union[str, int]] = attr.ib(init=False, default=None)

    CRAWL_DEPTH_FIELD: ClassVar[str] = "crawl_depth"

    async def wait_for_populated_q(self, wait_time: Union[int, float] = 60) -> None:
        """Waits for the q to become populated by polling exhausted at wait_time intervals.

        :param wait_time: The interval time in seconds for polling exhausted. Defaults to 60
        """
        logger.info(
            f"RedisFrontier[wait_for_populated_q]: starting wait loop, checking every {wait_time} seconds"
        )
        while await self.exhausted():
            logger.info(
                f"RedisFrontier[wait_for_populated_q]: q still empty, waiting another {wait_time} seconds"
            )
            await asyncio.sleep(wait_time, loop=self.loop)
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
        return await self.redis.llen(self.q_key)

    async def exhausted(self) -> bool:
        """Returns a boolean that indicates if the frontier is exhausted or not"""
        return await self.redis.llen(self.q_key) == 0

    async def is_seen(self, url: str) -> bool:
        """Returns an Awaitable that resolves with a boolean that indicates if the supplied URL has been seen or not"""
        return await self.redis.sismember(self.seen_key, url) == 1

    def add_to_pending(self, url: str) -> Awaitable[None]:
        """Add the supplied URL to the pending set

        :param url: The URL to add to the pending set
        """
        return self.redis.sadd(self.pending_key, url)

    def remove_from_pending(self, url: str) -> Awaitable[None]:
        """Remove the supplied URL from the pending set

        :param url: The URL to be removed from the pending set
        """
        return self.redis.srem(self.pending_key, url)

    async def _pop_url(self) -> Dict[str, Union[str, int]]:
        udict_str = await self.redis.lpop(self.q_key)
        return ujson.loads(udict_str)

    async def next_url(self) -> str:
        """Retrieve the next URL to be crawled from the frontier and updates the pending set

        :return: The next URL to be crawled
        """
        if self.currently_crawling is not None:
            logger.info(
                f"RedisFrontier[next_url]: removing the previous URL {self.currently_crawling} from the pending set"
            )
            curl: str = self.currently_crawling["url"]
            await self.remove_from_pending(curl)
        self.currently_crawling = await self._pop_url()
        logger.info(
            f"RedisFrontier[next_url]: the next URL is {self.currently_crawling}"
        )
        await self.add_to_pending(self.currently_crawling["url"])
        return self.currently_crawling["url"]

    async def init(self) -> None:
        """Initialize the frontier"""
        self.crawl_depth = int(
            await self.redis.hget(self.info_key, self.CRAWL_DEPTH_FIELD) or 0
        )
        logger.info(f"RedisFrontier[init]: crawl depth = {self.crawl_depth}")
        await self.scope.init()

    async def add(self, url: str, depth: int) -> None:
        """Conditionally adds a URL to frontier.

        The addition condition is not seen and in scope.

        :param url: The URL to maybe add to the frontier
        :param depth: The depth the URL is to be crawled at
        """
        should_add = self.scope.in_scope(url)
        if should_add and not await self.is_seen(url):
            await asyncio.gather(
                self.redis.rpush(self.q_key, ujson.dumps(dict(url=url, depth=depth))),
                self.redis.sadd(self.seen_key, url),
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
        add_to_seen: List[str] = []
        add_to_queue: List[str] = []
        for url in urls:
            is_seen = await self.is_seen(url)
            in_scope = self.scope.in_scope(url)
            logger.info(
                f'RedisFrontier[add_all]: {{"url": "{url}", "seen": '
                f'{is_seen}, "in_scope": {in_scope}, "depth": {next_depth}}}'
            )
            if in_scope and not is_seen:
                add_to_seen.append(url)
                add_to_queue.append(ujson.dumps(dict(url=url, depth=next_depth)))
        qlen = len(add_to_queue)
        logger.info(f"RedisFrontier[add_all]: adding {qlen} urls to the frontier")
        if qlen > 0:
            await asyncio.gather(
                self.redis.rpush(self.q_key, *add_to_queue),
                self.redis.sadd(self.seen_key, *add_to_seen),
                loop=self.loop,
            )

    def __attrs_post_init__(self) -> None:
        self.info_key = f"{self.autoid}:info"
        self.q_key = f"{self.autoid}:q"
        self.pending_key = f"{self.autoid}:qp"
        self.seen_key = f"{self.autoid}:seen"
        self.scope = RedisScope(self.redis, self.autoid)
