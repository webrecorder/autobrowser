from asyncio import AbstractEventLoop, CancelledError, TimeoutError, sleep
from typing import Any, Awaitable, Dict, Iterable, Optional, Union

from aioredis import Redis
from async_timeout import timeout
from ujson import loads

from autobrowser.automation import AutomationConfig, RedisKeys
from autobrowser.scope import RedisScope
from autobrowser.util import AutoLogger, Helper, create_autologger

__all__ = ["RedisFrontier"]

CRAWL_DEPTH_FIELD: str = "crawl_depth"


class RedisFrontier:
    __slots__ = [
        "__weakref__",
        "_did_wait",
        "config",
        "crawl_depth",
        "currently_crawling",
        "keys",
        "logger",
        "loop",
        "redis",
        "scope",
    ]

    def __init__(
        self,
        redis: Redis,
        config: AutomationConfig,
        loop: Optional[AbstractEventLoop] = None,
    ):
        """Initialize the new instance of RedisFrontier

        :param redis: The redis instance to be used
        :param config: The automation config
        :param loop: The event loop used by the automation
        """
        self.config: AutomationConfig = config
        self.crawl_depth: int = -1
        self.currently_crawling: Optional[Dict[str, Union[str, int]]] = None
        self.keys: RedisKeys = self.config.redis_keys
        self.logger: AutoLogger = create_autologger("frontier", "RedisFrontier")
        self.loop: AbstractEventLoop = Helper.ensure_loop(loop)
        self.redis: Redis = redis
        self.scope: RedisScope = RedisScope(self.redis, self.keys)
        self._did_wait: bool = False

    @property
    def did_wait(self) -> bool:
        """Returns T/F indicating if the frontier has waited for the q to become
        populated already.

        :return: T/F indicating if the q population wait has been performed
        """
        return self._did_wait

    def crawling_new_page(self, page_url: str) -> None:
        """Indicate to both the frontier and scope instances for the crawl
        that we are now crawling a new page.

        This is used for tracking inner page links
        """
        self.scope.crawling_new_page(page_url)

    def next_depth(self) -> int:
        """Returns the next depth by adding one to the depth of the currently crawled URLs depth

        :return: The next depth
        """
        if self.currently_crawling is not None:
            return self.currently_crawling["depth"] + 1
        return -1

    def add_to_pending(self, url: str) -> Awaitable[Any]:
        """Add the supplied URL to the pending set

        :param url: The URL to add to the pending set
        """
        self.logger.debug("add_to_pending", f"Adding {url} to the pending set")
        return self.redis.sadd(self.keys.pending, url)

    def remove_from_pending(self, url: str) -> Awaitable[Any]:
        """Remove the supplied URL from the pending set

        :param url: The URL to be removed from the pending set
        """
        return self.redis.srem(self.keys.pending, url)

    def pop_inner_page_link(self) -> Awaitable[Optional[str]]:
        """Removes and returns an inner page links from the redis set"""
        return self.redis.spop(self.keys.inner_page_links)

    async def have_inner_page_links(self) -> bool:
        """Returns T/F indicating if we have inner page links

        :return: T/F indicating if we have inner page links
        """
        num_ipls = await self.redis.scard(self.keys.inner_page_links)
        return num_ipls > 0

    async def remove_inner_page_links(self) -> None:
        """Removes the inner page links set from redis"""
        await self.redis.delete(self.keys.inner_page_links)

    async def wait_for_populated_q(
        self, max_time: Union[int, float] = 60, poll_rate: Union[int, float] = 5
    ) -> bool:
        """Waits for the q to become populated by polling exhausted at poll_rate intervals until the
        frontier becomes populated or max_time is reached

        :param max_time: The maximum amount of time to wait for the frontier to become populated.
        Defaults to 60
        :param poll_rate: The interval time in seconds for polling exhausted. Defaults to 5
        :return: T/F indicating if the frontier is still exhausted or not
        """
        logged_method = "wait_for_populated_q"
        self.logger.info(
            logged_method,
            f"starting wait loop [max_time={max_time}, poll_rate={poll_rate}]",
        )
        try:
            if max_time != -1:
                async with timeout(max_time):
                    await self._wait_for_populated_q(logged_method, poll_rate)
            else:
                # we wait for ever when max_time is -1
                await self._wait_for_populated_q(logged_method, poll_rate)
        except (CancelledError, TimeoutError):
            self.logger.info(logged_method, f"timed out")
        except Exception as e:
            self.logger.exception(logged_method, f"waiting for ", exc_info=e)
            raise
        q_len = await self.q_len()
        self.logger.info(
            logged_method, f"done waiting we have a q populated with {q_len} URLs"
        )
        return q_len == 0

    async def q_len(self) -> int:
        """Returns an Awaitable that resolves to the length of the frontier's q

        :return: The length of the queue
        """
        return await self.redis.llen(self.keys.queue)

    async def exhausted(self) -> bool:
        """Returns a boolean that indicates if the frontier is exhausted or not

        :return: T/F indicating if the frontier is exhausted
        """
        qlen = await self.redis.llen(self.keys.queue)
        self.logger.debug("exhausted", f"len(queue) = {qlen}")
        return qlen == 0

    async def is_seen(self, url: str) -> bool:
        """Returns an Awaitable that resolves with a boolean that indicates if
        the supplied URL has been seen or not

        :return: T/F indicating if the supplied URL is seen
        """
        return await self.redis.sismember(self.keys.seen, url) == 1

    async def next_url(self) -> str:
        """Retrieve the next URL to be crawled from the frontier and updates the pending set

        :return: The next URL to be crawled
        """
        self.currently_crawling = await self._pop_url()
        self.logger.debug(
            "next_url", f"the next URL is {Helper.json_string(self.currently_crawling)}"
        )
        cc_url: str = self.currently_crawling["url"]
        await self.add_to_pending(cc_url)
        return cc_url

    async def remove_current_from_pending(self) -> None:
        """If currently_crawling url is set, remove it from pending set"""
        if self.currently_crawling is not None:
            self.logger.debug(
                "next_url",
                f"removing the previous URL {self.currently_crawling} from the pending set",
            )
            curl: str = self.currently_crawling["url"]
            await self.remove_from_pending(curl)
            self.currently_crawling = None

    async def init(self) -> bool:
        """Initialize the frontier. Returns T/F indicating
        if the frontier is currently exhausted

        """
        self.crawl_depth = int(
            await self.redis.hget(self.keys.info, CRAWL_DEPTH_FIELD) or -1
        )
        self.logger.info("init", f"crawl depth = {self.crawl_depth}")
        await self.scope.init()
        if self.config.wait_for_q is not None:
            return await self.wait_for_populated_q(
                self.config.wait_for_q, self.config.wait_for_q_poll_rate
            )
        return await self.exhausted()

    async def add(self, url: str, depth: int) -> bool:
        """Conditionally adds a URL to frontier.

        The addition condition is not seen, in scope, and not an
        inner page link.

        If the supplied URL is an inner page link it is added
        to the inner page links set.

        :param url: The URL to maybe add to the frontier
        :param depth: The depth the URL is to be crawled at
        :return: T/F indicating if the URL @ depth was added to the frontier
        """
        logged_method = "add"
        url_info = Helper.json_string(url=url, depth=depth, page=self.scope.current_page)

        in_scope = self.scope.in_scope(url)
        if not in_scope:
            self.logger.info(
                logged_method,
                f"Not adding URL to the frontier, not in scope - {url_info}",
            )
            return False

        if self.scope.is_inner_page_link(url):
            await self.redis.sadd(self.keys.inner_page_links, url)
            self.logger.info(
                logged_method,
                f"Not adding URL to the frontier, inner page link - {url_info}",
            )
            return False

        was_added = await self.redis.sadd(self.keys.seen, url)
        if was_added == 0:
            self.logger.info(
                logged_method, f"Not adding URL to the frontier, seen - {url_info}"
            )
            return False

        await self.redis.rpush(self.keys.queue, url_info)
        self.logger.info(logged_method, f"Added URL to the frontier - {url_info}")
        return True

    async def add_all(self, urls: Iterable[str]) -> bool:
        """Conditionally adds URLs to frontier.

        The addition condition is not seen and in scope.

        :param urls: An iterable containing URLs to be added
        to the frontier
        :return: T/F indicating if any of the URLs @ next depth were added to the frontier
        """
        logged_method = "add_all"
        next_depth = self.next_depth()
        if self.crawl_depth != -1 and next_depth > self.crawl_depth:
            self.logger.info(
                logged_method,
                f"Not adding any URLs, maximum crawl depth exceeded. Max depth = {self.crawl_depth}",
            )
            return False

        self.logger.debug(
            logged_method,
            f"The next depth is {next_depth}. Max depth = {self.crawl_depth}",
        )

        add_to_frontier = self.add
        num_added = 0

        for url in urls:
            was_added = await add_to_frontier(url, next_depth)
            if was_added:
                num_added += 1

        if num_added > 0:
            self.logger.debug(logged_method, f"Added {num_added} urls to the frontier")
            return True

        self.logger.debug(logged_method, f"No URLs added to the frontier")
        return False

    async def _pop_url(self) -> Dict[str, Union[str, int]]:
        """Pops (removes) the next URL to be crawled from
        the queue and returns it

        :return: The next URL to be crawled
        """
        udict_str = await self.redis.lpop(self.keys.queue)
        return loads(udict_str)

    async def _wait_for_populated_q(
        self, logged_method: str, poll_rate: Union[int, float] = 5
    ):
        """Performs the polling of the frontiers Q to check for when
        it becomes populated

        :param logged_method: The method name that should be used rather than this one
        :param poll_rate: The amount of time between checks
        """
        frontier_exhausted = await self.exhausted()
        eloop = self.loop
        is_frontier_exhausted = self.exhausted
        self_logger_info = self.logger.info

        while frontier_exhausted:
            self_logger_info(logged_method, "q still not populated waiting")
            await sleep(poll_rate, loop=eloop)
            frontier_exhausted = await is_frontier_exhausted()

    def __str__(self) -> str:
        return f"RedisFrontier()"

    def __repr__(self) -> str:
        return self.__str__()
