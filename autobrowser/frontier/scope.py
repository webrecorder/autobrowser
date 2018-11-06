from typing import Set, List, Pattern

import attr
from aioredis import Redis
from urlcanon.parse import parse_url
from re import compile

surt_end = b")"

__all__ = ["Scope"]


@attr.dataclass(slots=True)
class Scope(object):
    surts: Set[bytes] = attr.ib()

    @staticmethod
    def from_seeds(seed_list: List[str]) -> "Scope":
        new_list: Set[bytes] = set()
        for url in seed_list:
            surt = parse_url(url).surt(with_scheme=False)
            new_list.add(surt[0 : surt.index(surt_end) + 1])
        return Scope(new_list)

    def in_scope(self, url: str) -> bool:
        usurt = parse_url(url).surt(with_scheme=False)
        for surt in self.surts:
            if usurt.startswith(surt):
                return True
        return False


@attr.dataclass(slots=True)
class RedisScope(object):
    redis: Redis = attr.ib()
    scope_key: str = attr.ib(convert=lambda uid: f"{uid}:scope")
    scope_values: Set[Pattern] = attr.ib(init=False, factory=set)

    async def retrieve_scope_values(self) -> None:
        sv = await self.redis.smembers(self.scope_key)
        for p in sv:
            self.scope_values.add(compile(p))

    def in_scope(self, url: str) -> bool:
        for pattern in self.scope_values:
            if pattern.match(url):
                return True
        return False
