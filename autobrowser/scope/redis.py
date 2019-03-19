from typing import List
from ujson import loads as ujson_loads

from aioredis import Redis
from attr import dataclass as attr_dataclass, ib as attr_ib
from urlcanon import MatchRule

from autobrowser.automation import RedisKeys
from autobrowser.util import AutoLogger, create_autologger

__all__ = ["RedisScope"]


@attr_dataclass(slots=True)
class RedisScope:
    redis: Redis = attr_ib(repr=False)
    keys: RedisKeys = attr_ib()
    rules: List[MatchRule] = attr_ib(init=False, factory=list)
    all_links: bool = attr_ib(init=False, default=False)
    logger: AutoLogger = attr_ib(init=False, default=None)

    async def init(self) -> None:
        """Initialize the scope class.

        Retrieves all scope rules from the scope field and populates the rules list.
        If the retrieved scope rules is zero then all links are considered in scope.
        """
        logged_method = "init"

        self_logger_info = self.logger.info
        add_rule = self.rules.append

        for scope_str in await self.redis.smembers(self.keys.scope):
            scope = ujson_loads(scope_str)
            self_logger_info(logged_method, f"creating scope rule <rule={scope_str}>")
            add_rule(MatchRule(**scope))
        num_rules = len(self.rules)
        self.all_links = num_rules == 0
        self_logger_info(
            logged_method,
            f"initialized <num rules={num_rules}, all links={self.all_links}>",
        )

    def in_scope(self, url: str) -> bool:
        """Determines if the URL is in scope

        :param url: The url to be tested
        :return: True if the URL is in scope or false if it is not in scope or is filtered
        """
        if self.all_links:
            return True
        for rule in self.rules:
            if rule.applies(url):
                return True
        return False

    def __attrs_post_init__(self) -> None:
        self.logger = create_autologger("scope", "RedisScope")
