# -*- coding: utf-8 -*-
import asyncio
from asyncio import Future
from typing import Optional, Set

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
        """

        :param client:
        :param num_inflight:
        :param idle_time:
        :param global_wait:
        :return:
        """
        niw = cls(
            client=client,
            num_inflight=num_inflight,
            idle_time=idle_time,
            global_wait=global_wait,
        )
        return niw._create_idle_future()

    def _create_idle_future(self) -> Future:
        """"""
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
        if not self._idle_future.done():
            self._idle_future.set_result(True)

    async def _global_to_wait(self) -> None:
        """"""
        try:
            async with async_timeout.timeout(self.global_wait, loop=self.loop):
                await self._idle_future
        except Exception as e:
            self.emit("idle")

        self.requestIds.clear()

    async def _start_timeout(self) -> None:
        """"""
        await asyncio.sleep(self.idle_time, loop=self.loop)
        self.emit("idle")

    def req_started(self, info: dict) -> None:
        """

        :param info:
        :return:
        """
        self.requestIds.add(info["requestId"])
        if len(self.requestIds) > self.num_inflight and self._to:
            self._to.cancel()
            self._to = None

    def req_finished(self, info: dict) -> None:
        """

        :param info:
        :return:
        """
        rid = info["requestId"]
        if rid in self.requestIds:
            self.requestIds.remove(rid)
        if len(self.requestIds) <= self.num_inflight and self._to is None:
            self._to = asyncio.ensure_future(self._start_timeout(), loop=self.loop)


def monitor(
    client: Client, num_inflight: int = 2, idle_time: int = 1, global_wait: int = 40
) -> Future:
    return NetworkIdleMonitor.monitor(
        client=client,
        num_inflight=num_inflight,
        idle_time=idle_time,
        global_wait=global_wait,
    )
