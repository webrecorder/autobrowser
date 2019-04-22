from asyncio import AbstractEventLoop, Event
from signal import SIGINT, SIGTERM
from typing import Any, Optional

from autobrowser.util import Helper

__all__ = ["ShutdownCondition"]


class ShutdownCondition:
    """This class represents an abstraction around the two conditions that would cause driver
    process to shutdown.

    Shutdown conditions:
      - when the process receives the SIGTERM signal triggering an immediate shutdown.
      - when all Tabs controlled by the driver have finished their task.
    """

    __slots__ = ["__weakref__", "_shutdown_event", "_shutdown_from_signal", "loop"]

    def __init__(self, loop: Optional[AbstractEventLoop] = None) -> None:
        """Initialize the new ShutdownCondition instance

        :param loop: The event loop used by the automation
        """
        self.loop: AbstractEventLoop = Helper.ensure_loop(loop)
        self._shutdown_event: Event = Event(loop=self.loop)
        self._shutdown_from_signal: bool = False

        # SIGINT for local debugging
        self.loop.add_signal_handler(SIGINT, self._initiate_shutdown_signal)
        self.loop.add_signal_handler(SIGTERM, self._initiate_shutdown_signal)

    @property
    def shutdown_condition_met(self) -> bool:
        """Returns T/F indicating if the shutdown condition has been met"""
        return self._shutdown_event.is_set()

    @property
    def shutdown_from_signal(self) -> bool:
        """Returns T/F indicating if the shutdown was initiated by signal"""
        return self._shutdown_from_signal

    def initiate_shutdown(self) -> None:
        """Initiates the shutdown of the automation"""
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()

    def _initiate_shutdown_signal(self) -> None:
        """Initiates the shutdown of the automation when the
        shutdown signal was received"""
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()

    def __await__(self) -> Any:
        return self.loop.create_task(self._shutdown_event.wait()).__await__()
