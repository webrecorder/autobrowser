import logging
import ujson
from typing import Set, List

import attr
from aioredis import Redis
from urlcanon import parse_url, MatchRule

surt_end = b")"

__all__ = ["Scope", "RedisScope"]


logger = logging.getLogger("autobrowser")


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


def to_redis_key(aid: str) -> str:
    return f"{aid}: scope"


@attr.dataclass(slots=True)
class RedisScope(object):
    redis: Redis = attr.ib(repr=False)
    scope_key: str = attr.ib(convert=to_redis_key)
    rules: List[MatchRule] = attr.ib(init=False, factory=list)
    all_links: bool = attr.ib(init=False, default=False)

    async def init(self) -> None:
        """Initialize the scope class.

        Retrieves all scope rules from the scope field and populates the rules list.
        If the retrieved scope rules is zero then all links are considered in scope.
        """
        for scope_str in await self.redis.smembers(self.scope_key):
            scope = ujson.loads(scope_str)
            self.rules.append(MatchRule(**scope))
        num_rules = len(self.rules)
        self.all_links = num_rules == 0
        logger.info(
            f"RedisScope[init]: retrieved {num_rules} rules, all links = {self.all_links}"
        )

    def in_scope(self, url: str) -> bool:
        """Determines if the URL is in scope

        :param url: The url to be tested
        :return: True if the URL is in scope or false if it is not in scope or is filtered
        """
        if url.endswith("#timeline"):  # (FIXME) this is for twitter niceness
            return False
        if self.all_links:
            return True
        in_scope = False
        for rule in self.rules:
            in_scope = rule.applies(url)
            if in_scope:
                break
        return in_scope
