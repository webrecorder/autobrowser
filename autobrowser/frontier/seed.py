from typing import Set

import attr
from yarl import URL


@attr.dataclass(slots=True)
class Seed(object):
    url: str = attr.ib()
    mode: str = attr.ib()
    depth: int = attr.ib()
    seen: Set[str] = attr.ib(init=False, factory=set)
    url_count: int = attr.ib(init=False, default=1)

    def crawled_url(self) -> None:
        self.url_count -= 1

    def seen_url(self, url: str) -> bool:
        return url in self.seen

    def add_to_seen(self, url: str) -> None:
        self.seen.add(url)
        self.url_count += 1

    @property
    def done(self) -> bool:
        return self.url_count == 0

