import ujson
from typing import Set, List

import attr
from aioredis import Redis
from urlcanon import parse_url, MatchRule

surt_end = b")"

__all__ = ["Scope", "RedisScope"]


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
    rules: List[MatchRule] = attr.ib(init=False, factory=list)

    async def init(self) -> None:
        """Initialize the scope class.

        Retrieves all scope rules from the scope field and populates the rules list
        """
        sv = await self.redis.smembers(self.scope_key)
        for scope_str in sv:
            scope = ujson.loads(scope_str)
            if scope["type"] == "regex":
                self.rules.append(MatchRule(regex=scope["value"]))
            else:
                self.rules.append(MatchRule(surt=scope["value"]))

    def in_scope(self, url: str) -> bool:
        """Determines if the URL is in scope

        :param url: The url to be tested
        :return: True if the URL is in scope or false if it is not in scope or is filtered
        """
        in_scope = False
        for rule in self.rules:
            in_scope = rule.applies(url)
            if in_scope:
                break
        return in_scope
