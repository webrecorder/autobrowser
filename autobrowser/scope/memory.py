import logging
from typing import List, Set

import attr
from urlcanon import parse_url

surt_end = b")"

__all__ = ["Scope"]


logger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True)
class Scope:
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
