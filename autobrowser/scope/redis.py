from typing import Dict, List, Union

from aioredis import Redis
from attr import dataclass as attr_dataclass, ib as attr_ib
from ujson import loads as ujson_loads
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

        add_rule = self.add_scope_rule
        rules = await self.redis.smembers(self.keys.scope)

        for scope_rule_str in rules:
            add_rule(scope_rule_str)

        num_rules = len(self.rules)
        self.all_links = num_rules == 0
        self.logger.info(
            "init", f"initialized <num rules={num_rules}, all links={self.all_links}>"
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

    def add_scope_rule(self, scope_rule: Union[str, Dict, MatchRule]) -> None:
        """Creates a new urlcanon.MatchRule using the supplied scope rule and
        adds it to list of rules

        :param scope_rule:
        :return:
        """
        if isinstance(scope_rule, str):
            the_rule = MatchRule(**ujson_loads(scope_rule))
        elif isinstance(scope_rule, dict):
            the_rule = MatchRule(**scope_rule)
        else:
            the_rule = scope_rule
        self.logger.info("add_scope_rule", f"adding rule={the_rule}")
        self.rules.append(the_rule)

    def __attrs_post_init__(self) -> None:
        self.logger = create_autologger("scope", "RedisScope")
