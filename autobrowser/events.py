import attr

__all__ = ["BrowserEvents", "TabEvents"]


@attr.dataclass(slots=True, frozen=True)
class BrowserEvents:
    """The events emitted by browser instances"""

    Exiting: str = attr.ib(default="Browser:Exit")


@attr.dataclass(slots=True, frozen=True)
class TabEvents:
    """The events emitted by tab instances"""

    Closed: str = attr.ib(default="Tab:Closed")
