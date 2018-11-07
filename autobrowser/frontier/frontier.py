import asyncio
from typing import Set, Tuple, List, Awaitable, ClassVar

import attr
from aioredis import Redis

from .scope import Scope, RedisScope


@attr.dataclass(slots=True)
class Frontier(object):
    scope: Scope = attr.ib()
    depth: int = attr.ib()
    seen: Set[str] = attr.ib(init=False, factory=set)
    queue: List[Tuple[str, int]] = attr.ib(init=False, factory=list)
    running: Tuple[str, int] = attr.ib(init=False, default=None)

    async def init(self) -> None:
        pass

    async def exhausted(self) -> bool:
        return len(self.queue) == 0

    async def next_url(self) -> str:
        next_url = self.queue.pop()
        self.running = next_url
        return next_url[0]

    async def add(self, url: str, depth: int, scope: bool = True) -> None:
        should_add = self.scope.in_scope(url) if scope else True
        if should_add and url not in self.seen:
            self.queue.append((url, depth))
            self.seen.add(url)

    async def add_all(self, urls: List[str]) -> None:
        next_depth = self.running[1] + 1
        if next_depth > self.depth:
            return
        for url in urls:
            await self.add(url, depth=next_depth)

    @staticmethod
    def init_(depth: int, seed_list: List[str]) -> "Frontier":
        frontier = Frontier(Scope.from_seeds(seed_list), depth)
        for url in seed_list:
            frontier.queue.append((url, 0))
            frontier.seen.add(url)
        return frontier


@attr.dataclass(slots=True)
class RedisFrontier(object):
    redis: Redis = attr.ib(repr=False)
    autoid: str = attr.ib(convert=lambda aid: f"a:{aid}")
    scope: RedisScope = attr.ib(init=False)
    info_key: str = attr.ib(init=False, default=None)
    q_key: str = attr.ib(init=False, default=None)
    pending_key: str = attr.ib(init=False, default=None)
    seen_key: str = attr.ib(init=False, default=None)
    crawl_depth: int = attr.ib(init=False, default=-1)
    currently_crawling: str = attr.ib(init=False, default=None)

    CRAWL_DEPTH_FIELD: ClassVar[str] = "crawl_depth"

    @scope.default
    def scope_init(self) -> RedisScope:
        """Default value for our scope attribute"""
        return RedisScope(self.redis, self.autoid)

    def next_depth(self) -> int:
        if self.currently_crawling is not None:
            return (
                int(self.currently_crawling[self.currently_crawling.rindex(":") + 1])
                + 1
            )
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

    async def next_url(self) -> str:
        """Retrieve the next URL to be crawled from the frontier and updates the pending set

        :return: The next URL to be crawled
        """
        if self.currently_crawling is not None:
            await self.remove_from_pending(self.currently_crawling)
        self.currently_crawling = next_url = await self.redis.lpop(self.q_key)
        await self.add_to_pending(next_url)
        return next_url[: next_url.rindex(":")]

    async def init(self) -> None:
        """Initialize the frontier"""
        self.crawl_depth = int(await self.redis.hget(self.info_key, self.CRAWL_DEPTH_FIELD))
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
                self.redis.rpush(self.q_key, f"{url}:{depth}"),
                self.redis.sadd(self.seen_key, url),
            )

    async def add_all(self, urls: List[str]) -> None:
        """Conditionally adds a list of URLs to frontier.

        The addition condition is not seen and in scope.

        :param urls: The list of discovered URL to maybe add to the frontier
        """
        next_depth = self.next_depth()
        if next_depth > self.crawl_depth:
            return
        add_to_seen: List[str] = []
        add_to_queue: List[str] = []
        for url in urls:
            is_seen = await self.is_seen(url)
            if self.scope.in_scope(url) and not is_seen:
                print(f"adding {url}:{next_depth}")
                add_to_seen.append(url)
                add_to_queue.append(f"{url}:{next_depth}")
        if len(add_to_queue) > 0:
            await asyncio.gather(
                self.redis.rpush(self.q_key, *add_to_queue),
                self.redis.sadd(self.seen_key, *add_to_seen),
            )

    def __attrs_post_init__(self):
        self.info_key = f"{self.autoid}:info"
        self.q_key = f"{self.autoid}:q"
        self.pending_key = f"{self.autoid}:qp"
        self.seen_key = f"{self.autoid}:seen"
