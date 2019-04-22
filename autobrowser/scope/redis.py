from typing import Dict, List, Union

from aioredis import Redis
from ujson import loads
from urlcanon import MatchRule
from urlcanon.canon import remove_fragment, whatwg

from autobrowser.automation import RedisKeys
from autobrowser.util import AutoLogger, create_autologger

__all__ = ["RedisScope"]


def strip_frag(url: str) -> str:
    """Removed the fragment from the supplied URL if it exists

    :param url: The URL to have the fragment removed
    :return: The fragmentless URL
    """
    cannond = whatwg.canonicalize(url)
    remove_fragment(cannond)
    return str(cannond)


class RedisScope:
    __slots__ = [
        "__weakref__",
        "_current_page",
        "all_links",
        "keys",
        "logger",
        "redis",
        "rules",
    ]

    def __init__(self, redis: Redis, keys: RedisKeys) -> None:
        """Initialize the new instance of RedisScope

        :param redis: The redis instance to be used
        :param keys: The redis keys class containing the keys for the automation
        """
        self.redis: Redis = redis
        self.keys: RedisKeys = keys
        self.rules: List[MatchRule] = []
        self.all_links: bool = False
        self.logger: AutoLogger = create_autologger("scope", "RedisScope")
        self._current_page: str = ""

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
            the_rule = MatchRule(**loads(scope_rule))
        elif isinstance(scope_rule, dict):
            the_rule = MatchRule(**scope_rule)
        else:
            the_rule = scope_rule
        self.logger.info("add_scope_rule", f"adding rule={the_rule}")
        self.rules.append(the_rule)

    def is_inner_page_link(self, url: str) -> bool:
        """Returns T/F indicating if the supplied outlink URL
        is a inner page link.

        :param url: The outlink URL to be tested
        :return: T/F indicating if the supplied outlink URL
        is a inner page link.
        """
        canonicalized = whatwg.canonicalize(url)
        hash_frag = (canonicalized.hash_sign + canonicalized.fragment).decode("utf-8")
        if not hash_frag:
            return False
        remove_fragment(canonicalized)
        return str(canonicalized) == self._current_page

    def crawling_new_page(self, current_page: str) -> None:
        """Informs this instance of RedisScope that the crawler
        is crawling a new page

        :param current_page: The URL to the page being crawled
        """
        self._current_page = strip_frag(current_page)

    def __str__(self) -> str:
        return f"RedisScope(current_page={self._current_page}, all_links={self.all_links}, rules={len(self.rules)})"

    def __repr__(self) -> str:
        return self.__str__()
