from typing import Set, Tuple, List, Union

import attr
from aioredis import Redis

from .scope import Scope


@attr.dataclass(slots=True)
class Frontier(object):
    scope: Scope = attr.ib()
    depth: int = attr.ib()
    seen: Set[str] = attr.ib(init=False, factory=set)
    queue: List[Tuple[str, int]] = attr.ib(init=False, factory=list)
    running: Tuple[str, int] = attr.ib(init=False, default=None)

    @property
    def exhausted(self) -> bool:
        return len(self.queue) == 0

    def pop(self) -> str:
        next_url = self.queue.pop()
        self.running = next_url
        return next_url[0]

    def add(self, url: str, depth: int, scope: bool = True) -> None:
        should_add = self.scope.in_scope(url) if scope else True
        if should_add and url not in self.seen:
            self.queue.append((url, depth))
            self.seen.add(url)

    def add_all(self, urls: List[str]) -> None:
        next_depth = self.running[1] + 1
        if next_depth > self.depth:
            return
        for url in urls:
            self.add(url, depth=next_depth)

    @staticmethod
    def init(depth: int, seed_list: List[str]) -> "Frontier":
        frontier = Frontier(Scope.from_seeds(seed_list), depth)
        for url in seed_list:
            frontier.queue.append((url, 0))
            frontier.seen.add(url)
        return frontier


@attr.dataclass(slots=True)
class RedisFrontier(object):
    redis: Redis = attr.ib()
    uid: str = attr.ib(convert=lambda _uid: f"a:{_uid}")
    q_key: str = attr.ib(init=False, default=None)
    pending_key: str = attr.ib(init=False, default=None)
    seen_key: str = attr.ib(init=False, default=None)
    scope_key: str = attr.ib(init=False, default=None)
    _loc_len: int = attr.ib(init=False, default=-1)
    _loc_depth: int = attr.ib(init=False, default=-1)

    async def exhausted(self) -> bool:
        return await self.redis.llen(self.q_key) == 0

    async def is_seen(self, url: str) -> bool:
        return await self.redis.sismember(self.seen_key, url) == 1

    async def add_to_pending(self, url: str) -> None:
        await self.redis.sadd(self.pending_key, url)

    async def remove_from_pending(self, url: str) -> None:
        await self.redis.srem(self.pending_key, url)

    async def local_populate_frontier(self, depth: int, seed_list: List[str]):
        self._loc_depth = depth
        self._loc_len = len(seed_list)
        for url in seed_list:
            await self.redis.rpush(self.q_key, f"{url}:0")
            await self.redis.sadd(self.scope_key, url)

    def __attrs_post_init__(self):
        self.q_key = f"{self.uid}:q"
        self.pending_key = f"{self.uid}:qp"
        self.seen_key = f"{self.uid}:seen"
        self.scope_key = f"{self.uid}:scope"
