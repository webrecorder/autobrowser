# -*- coding: utf-8 -*-
import asyncio
from asyncio import Future
from typing import Optional, Set, Dict

import async_timeout
from cripy import Client
from pyee import EventEmitter

from .helper import Helper

__all__ = ["NetworkIdleMonitor", "monitor"]


class NetworkIdleMonitor(EventEmitter):
    """Monitors the network requests of the remote browser to determine when
    network idle happens"""

    def __init__(
        self,
        client: Client,
        num_inflight: int = 2,
        idle_time: int = 1,
        global_wait: int = 60,
    ) -> None:
        """Construct a new Network Idle monitor

        :param client: The chrome remote interface python client instance to use
        :param num_inflight: The number of inflight requests to wait for to start
        the idle count down
        :param idle_time: Time in seconds to wait for no more requests to be made
        for network idle
        :param global_wait: Time in seconds to wait unconditionally before emitting
        network idle
        """
        self.loop = asyncio.get_event_loop()
        super().__init__(loop=self.loop)
        self.client = client
        self.requestIds: Set[str] = set()
        self.num_inflight = num_inflight
        self.idle_time = idle_time
        self.global_wait = global_wait
        self._to: Optional[Future] = None
        self._idle_future: Optional[Future] = None

    @classmethod
    def monitor(
        cls,
        client: Client,
        num_inflight: int = 2,
        idle_time: int = 1,
        global_wait: int = 40,
    ) -> Future:
        """Returns a future that resolves once network idle has been determined

        :param client: The chrome remote interface python client instance to use
        :param num_inflight: The number of inflight requests to wait for to start
        the idle count down
        :param idle_time: Time in seconds to wait for no more requests to be made
        for network idle
        :param global_wait: Time in seconds to wait unconditionally before emitting
        network idle
        """
        niw = cls(
            client=client,
            num_inflight=num_inflight,
            idle_time=idle_time,
            global_wait=global_wait,
        )
        return niw._create_idle_future()

    def _create_idle_future(self) -> Future:
        """Creates and returns the global wait future that resolves once
        newtwork idle has been emitted or the global wait time has been
        reached

        :return: A future
        """
        listeners = [
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
        self._idle_future = self.loop.create_future()
        self._idle_future.add_done_callback(
            lambda f: Helper.remove_event_listeners(listeners)
        )

        self.once("idle", self.idle_cb)

        return asyncio.ensure_future(self._global_to_wait(), loop=self.loop)

    def idle_cb(self) -> None:
        """Sets the idle future results to done"""
        if not self._idle_future.done():
            self._idle_future.set_result(True)

    async def _global_to_wait(self) -> None:
        """Coroutine that waits for the idle future to resolve or
        global wait time to be hit
        """
        try:
            async with async_timeout.timeout(self.global_wait, loop=self.loop):
                await self._idle_future
        except Exception as e:
            self.emit("idle")

        self.requestIds.clear()

    async def _start_timeout(self) -> None:
        """Starts the idle time wait and if this Coroutine is not canceled
        and the idle time elapses the idle event is emitted signifying
        network idle has been reached
        """
        await asyncio.sleep(self.idle_time, loop=self.loop)
        self.emit("idle")

    def req_started(self, info: Dict) -> None:
        """Listener for the Network.requestWillBeSent events

        :param info: The request info supplied by the CDP
        """
        self.requestIds.add(info["requestId"])
        if len(self.requestIds) > self.num_inflight and self._to:
            self._to.cancel()
            self._to = None

    def req_finished(self, info: Dict) -> None:
        """Listener for the Network.loadingFinished and
        Network.loadingFailed events

        :param info: The request info supplied by the CDP
        """
        rid = info["requestId"]
        if rid in self.requestIds:
            self.requestIds.remove(rid)
        if len(self.requestIds) <= self.num_inflight and self._to is None:
            self._to = asyncio.ensure_future(self._start_timeout(), loop=self.loop)


def monitor(
    client: Client, num_inflight: int = 2, idle_time: int = 1, global_wait: int = 40
) -> Future:
    """Returns a future that resolves once network idle has been determined

    :param client: The chrome remote interface python client instance to use
    :param num_inflight: The number of inflight requests to wait for to start the
    idle count down
    :param idle_time: Time in seconds to wait for no more requests to be made for
    network idle
    :param global_wait: Time in seconds to wait unconditionally before emitting
    network idle
    """
    return NetworkIdleMonitor.monitor(
        client=client,
        num_inflight=num_inflight,
        idle_time=idle_time,
        global_wait=global_wait,
    )
