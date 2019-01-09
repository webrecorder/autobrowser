import asyncio
from asyncio import AbstractEventLoop, Future, Task
from typing import Optional, Set, Dict, List, Any

import async_timeout
from cripy import Client
from pyee import EventEmitter

from .helper import Helper, ListenerDict

__all__ = ["NetworkIdleMonitor", "monitor"]


class NetworkIdleMonitor(EventEmitter):
    """Monitors the network requests of the remote browser to determine when
    network idle happens"""

    def __init__(
        self,
        client: Client,
        num_inflight: int = 2,
        idle_time: int = 2,
        global_wait: int = 60,
        loop: Optional[AbstractEventLoop] = None,
    ) -> None:
        """Construct a new Network Idle monitor

        :param client: The chrome remote interface python client instance to use
        :param num_inflight: The number of inflight requests to wait for to start
        the idle count down
        :param idle_time: Time in seconds to wait for no more requests to be made
        for network idle
        :param global_wait: Time in seconds to wait unconditionally before emitting
        network idle
        :param loop:
        """
        super().__init__(loop=loop if loop is not None else asyncio.get_event_loop())
        self.client: Client = client
        self.requestIds: Set[str] = set()
        self.num_inflight: int = num_inflight
        self.idle_time: int = idle_time
        self.global_wait: int = global_wait
        self._to: Optional[Task] = None
        self._safety_task: Optional[Task] = None
        self._idle_future: Optional[Future] = None
        self.listeners: Optional[List[ListenerDict]] = None

    @classmethod
    def monitor(
        cls,
        client: Client,
        num_inflight: int = 2,
        idle_time: int = 2,
        global_wait: int = 60,
        loop: Optional[AbstractEventLoop] = None,
    ) -> Task:
        """Returns a future that resolves once network idle has been determined

        :param client: The chrome remote interface python client instance to use
        :param num_inflight: The number of inflight requests to wait for to start
        the idle count down
        :param idle_time: Time in seconds to wait for no more requests to be made
        for network idle
        :param global_wait: Time in seconds to wait unconditionally before emitting
        network idle
        :param loop:
        """
        niw = cls(
            client=client,
            num_inflight=num_inflight,
            idle_time=idle_time,
            global_wait=global_wait,
            loop=loop,
        )
        return niw.create_idle_future()

    def create_idle_future(self) -> Task:
        """Creates and returns the global wait future that resolves once
        newtwork idle has been emitted or the global wait time has been
        reached

        :return: A future
        """
        self._idle_future = self._loop.create_future()
        self.once("idle", self.idle_cb)
        return self._loop.create_task(self._global_to_wait())

    def idle_cb(self) -> None:
        """Sets the idle future results to done"""
        if not self._idle_future.done():
            self._idle_future.set_result(True)

    def clean_up(self, *args: Any, **kwargs: Any) -> None:
        """Cleans up after ourselves"""
        if self.listeners is not None:
            Helper.remove_event_listeners(self.listeners)
        if self._safety_task is not None and not self._safety_task.done():
            self._safety_task.cancel()
        if self._to is not None and not self._to.done():
            self._to.cancel()

    async def _global_to_wait(self) -> None:
        """Coroutine that waits for the idle future to resolve or
        global wait time to be hit
        """
        self._idle_future.add_done_callback(self.clean_up)
        self.listeners = [
            Helper.add_event_listener(
                self.client, "Network.requestWillBeSent", self.req_started
            ),
            Helper.add_event_listener(
                self.client, "Network.loadingFinished", self.req_finished
            ),
            Helper.add_event_listener(
                self.client, "Network.loadingFailed", self.req_finished
            ),
        ]

        try:
            self._safety_task = self._loop.create_task(self.safety())
            async with async_timeout.timeout(self.global_wait, loop=self._loop):
                await self._idle_future
        except asyncio.TimeoutError as e:
            self.emit("idle")

        self.requestIds.clear()
        if self._to is not None and not self._to.done():
            self._to.cancel()
            self._to = None

    async def safety(self) -> None:
        """Guards against waiting the full global wait time if the network was idle and stays idle"""
        await asyncio.sleep(5, loop=self._loop)
        if self._idle_future and not self._idle_future.done():
            self._idle_future.set_result(True)

    async def _start_timeout(self) -> None:
        """Starts the idle time wait and if this Coroutine is not canceled
        and the idle time elapses the idle event is emitted signifying
        network idle has been reached
        """
        await asyncio.sleep(self.idle_time, loop=self._loop)
        self.emit("idle")

    def req_started(self, info: Dict) -> None:
        """Listener for the Network.requestWillBeSent events

        :param info: The request info supplied by the CDP
        """
        # print(f'req_started {info["requestId"]}, {self.requestIds}')
        self.requestIds.add(info["requestId"])
        if len(self.requestIds) > self.num_inflight and self._to:
            self._to.cancel()
            self._to = None
        if self._safety_task is not None:
            self._safety_task.cancel()
            self._safety_task = None

    def req_finished(self, info: Dict) -> None:
        """Listener for the Network.loadingFinished and
        Network.loadingFailed events

        :param info: The request info supplied by the CDP
        """
        rid = info["requestId"]
        # print(f'req_finished {info["requestId"]}, {self.requestIds}')
        if rid in self.requestIds:
            self.requestIds.remove(rid)
        if len(self.requestIds) <= self.num_inflight and self._to is None:
            self._to = self._loop.create_task(self._start_timeout())


def monitor(
    client: Client,
    num_inflight: int = 2,
    idle_time: int = 2,
    global_wait: int = 60,
    loop: Optional[AbstractEventLoop] = None,
) -> Task:
    """Returns a future that resolves once network idle has been determined

    :param client: The chrome remote interface python client instance to use
    :param num_inflight: The number of inflight requests to wait for to start the
    idle count down
    :param idle_time: Time in seconds to wait for no more requests to be made for
    network idle
    :param global_wait: Time in seconds to wait unconditionally before emitting
    network idle
    :param loop:
    """
    return NetworkIdleMonitor.monitor(
        client=client,
        num_inflight=num_inflight,
        idle_time=idle_time,
        global_wait=global_wait,
        loop=loop
    )
