from typing import Set, List

import attr
from urlcanon.parse import parse_url

surt_end = b")"

__all__ = ["Scope"]


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
