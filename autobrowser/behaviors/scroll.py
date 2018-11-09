# -*- coding: utf-8 -*-
import asyncio
import logging

from .basebehavior import Behavior, JSBasedBehavior

__all__ = ["AutoScrollBehavior", "ScrollBehavior"]

logger = logging.getLogger("autobrowser")

# note(n0tan3rd):
#   Input.dispatchMouseEvent(type="mouseWheel", x=0, y=0, deltaX=-120, deltaY=-120)
#   is effectively the same as a mouse scroll (need to figure out correct x, y)
#   window.addEventListener("mousewheel", (event) => console.log(event), false);
# client.Input.dispatchMouseEvent(
#     type="mouseWheel",
#     x=148,
#     y=100,
#     clickCount=0,
#     button="none",
#     deltaX=120,
#     deltaY=120,
#     timestamp=time.time(),
# )


class ScrollBehavior(Behavior):
    """The scroll performed by this behavior is controlled by a flag contained in
    page itself."""

    SCROLL_COND = (
        "window.scrollY + window.innerHeight < "
        "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
    )
    SCROLL_INC = "window.scrollBy(0, 80)"
    SCROLL_SPEED = 0.2

    async def perform_action(self) -> None:
        while True:
            is_paused = await self.evaluate_in_page("window.__wr_scroll_paused")
            self._paused = bool(is_paused)

            if self._paused:
                print("Scroll Paused")
                await asyncio.sleep(1.0)
                continue

            should_scroll = await self.evaluate_in_page(self.SCROLL_COND)

            if not should_scroll:
                break

            await self.evaluate_in_page(self.SCROLL_INC)

            await asyncio.sleep(self.SCROLL_SPEED)
        self._finished()


class AutoScrollBehavior(JSBasedBehavior):
    """Automatically scrolls the page a maximum of 20 times or until no more scrolling can be done.

    Waits for network idle after each scroll invocation.
    """

    async def perform_action(self) -> None:
        await self.evaluate_in_page(self._resource)
        logger.info(f"AutoScrollBehavior[perform_action]: waiting for network_idle")
        await self.tab.net_idle(global_wait=20)
        logger.info(f"AutoScrollBehavior[perform_action]: network_idle")
        self._finished()
