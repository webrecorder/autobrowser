import asyncio
import signal
from asyncio import AbstractEventLoop, Event
from typing import Any

import attr

__all__ = ["ShutdownCondition"]


@attr.dataclass(slots=True, cmp=False)
class ShutdownCondition(object):
    """This class represents an abstraction around the two conditions that would cause driver
    process to shutdown.

    Shutdown conditions:
      - when the process receives the SIGTERM signal triggering an immediate shutdown.
      - when all Tabs controlled by the driver have finished their task.
    """

    loop: AbstractEventLoop = attr.ib(default=None)
    _shutdown_event: Event = attr.ib(init=False, default=None)
    _shutdown_from_signal: bool = attr.ib(init=False, default=False)

    @property
    def shutdown_condition_met(self) -> bool:
        return self._shutdown_event.is_set()

    @property
    def shutdown_from_signal(self) -> bool:
        return self._shutdown_from_signal

    def initiate_shutdown(self) -> None:
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()

    def _initiate_shutdown_signal(self) -> None:
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()

    def __await__(self) -> Any:
        return self.loop.create_task(self._shutdown_event.wait()).__await__()

    def __attrs_post_init__(self) -> None:
        if self.loop is None:
            self.loop = asyncio.get_event_loop()
        self._shutdown_event = Event(loop=self.loop)
        self.loop.add_signal_handler(signal.SIGTERM, self._initiate_shutdown_signal)
