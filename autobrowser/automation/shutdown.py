import signal
from asyncio import AbstractEventLoop, Event
from typing import Any, Callable

import attr

from autobrowser.util.helper import Helper

__all__ = ["ShutdownCondition"]


@attr.dataclass(slots=True, cmp=False)
class ShutdownCondition(object):
    """This class represents an abstraction around the two conditions that would cause driver
    process to shutdown.

    Shutdown conditions:
      - when the process receives the SIGTERM signal triggering an immediate shutdown.
      - when all Tabs controlled by the driver have finished their task.
    """

    loop: AbstractEventLoop = attr.ib(default=None, converter=Helper.ensure_loop)
    _pending_tasks: int = attr.ib(init=False, default=0)
    _shutdown_event: Event = attr.ib(init=False, default=None)

    @property
    def pending_tasks(self) -> int:
        return self._pending_tasks

    @property
    def shutdown_condition_met(self) -> bool:
        return self._shutdown_event.is_set() and self._pending_tasks == 0

    def initiate_shutdown(self) -> None:
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()

    def track_pending_task(self) -> Callable[[], None]:
        self._pending_tasks += 1
        return self._finished_task

    def _finished_task(self) -> None:
        if self._pending_tasks != 0:
            self._pending_tasks -= 1
            if self._pending_tasks == 0:
                self.initiate_shutdown()

    def __await__(self) -> Any:
        return self.loop.create_task(self._shutdown_event.wait()).__await__()

    def __attrs_post_init__(self) -> None:
        self._shutdown_event = Event(loop=self.loop)
        self.loop.add_signal_handler(signal.SIGTERM, self.initiate_shutdown)
