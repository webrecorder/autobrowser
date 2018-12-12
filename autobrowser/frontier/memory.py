import logging
from typing import Set, Tuple, List

import attr

from autobrowser.scope import Scope

__all__ = ['Frontier']


logger = logging.getLogger("autobrowser")


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


