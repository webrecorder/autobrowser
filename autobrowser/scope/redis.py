import logging
from ujson import loads as ujson_loads
from typing import List

import attr
from aioredis import Redis
from urlcanon import MatchRule

from autobrowser.automation import RedisKeys

surt_end = b")"

__all__ = ["RedisScope"]


logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True)
class RedisScope(object):
    redis: Redis = attr.ib(repr=False)
    keys: RedisKeys = attr.ib()
    rules: List[MatchRule] = attr.ib(init=False, factory=list)
    all_links: bool = attr.ib(init=False, default=False)

    async def init(self) -> None:
        """Initialize the scope class.

        Retrieves all scope rules from the scope field and populates the rules list.
        If the retrieved scope rules is zero then all links are considered in scope.
        """
        # https://wiki.python.org/moin/PythonSpeed/PerformanceTips: Avoiding dots...
        add_rule = self.rules.append
        log_info = logger.info
        for scope_str in await self.redis.smembers(self.keys.scope):
            scope = ujson_loads(scope_str)
            log_info(f"RedisScope scope_str: {scope_str}")
            add_rule(MatchRule(**scope))
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
