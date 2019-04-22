from typing import ClassVar

__all__ = ["Events"]


class Events:
    """A simple class for holding the events that are emitted by instances of Browsers or Tabs"""

    BrowserExiting: ClassVar[str] = "Browser:Exiting"
    TabClosed: ClassVar[str] = "Tab:Closed"
