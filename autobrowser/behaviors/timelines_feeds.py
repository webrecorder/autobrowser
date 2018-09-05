from .basebehavior import Behavior
import aiofiles
import logging
import os

logger = logging.getLogger("autobrowser")


class TwitterTimelineBehavior(Behavior):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._has_resource = True
        self._init: str = None
        self._did_init: bool = False
        self._done: bool = False

    async def load_resources(self):
        logger.debug(f"TwitterTimeline.load_resources")
        async with aiofiles.open(
            f"{os.path.dirname(__file__)}/behaviorjs/twitterTimeline.js", "r"
        ) as iin:
            self._init = await iin.read()
        logger.debug(f"TwitterTimeline.load_resources complete")

    async def run(self):
        logger.debug(f"TwitterTimeline.run")
        if not self._did_init:
            await self.tab.evaluate_in_page(self._init)
            self._did_init = True
        done = await self.tab.evaluate_in_page("window.$WRTIHandler$()")
        logger.debug(f"TwitterTimeline done ? {done}")
        if done.get("result").get("value"):
            self.tab.pause_behaviors()


class FBNewsFeedBehavior(Behavior):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._has_resource = True
        self._init: str = None
        self._did_init: bool = False
        self._done: bool = False

    async def load_resources(self):
        logger.debug(f"FBNewsFeed.load_resources")
        async with aiofiles.open(
            f"{os.path.dirname(__file__)}/behaviorjs/facebookNewsFeed.js", "r"
        ) as iin:
            self._init = await iin.read()
        logger.debug(f"FBNewsFeed.load_resources complete")

    async def run(self):
        logger.debug(f"FBNewsFeed.run")
        if not self._did_init:
            await self.tab.evaluate_in_page(self._init)
            self._did_init = True
        done = await self.tab.evaluate_in_page("window.$WRNFHandler$()")
        logger.debug(f"FBNewsFeed done ? {done}")
        if done.get("result").get("value"):
            self.tab.pause_behaviors()


class FBUserFeedBehavior(Behavior):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._has_resource = True
        self._init: str = None
        self._did_init: bool = False
        self._done: bool = False

    async def load_resources(self):
        logger.debug(f"FBUserFeed.load_resources")
        async with aiofiles.open(
            f"{os.path.dirname(__file__)}/behaviorjs/facebookUserFeed.js", "r"
        ) as iin:
            self._init = await iin.read()
        logger.debug(f"FBUserFeedBehavior.load_resources complete")

    async def run(self):
        logger.debug(f"FBUserFeed.run")
        if not self._did_init:
            await self.tab.evaluate_in_page(self._init)
            self._did_init = True
        done = await self.tab.evaluate_in_page("window.$WRTLHandler$()")
        logger.debug(f"FBUserFeed done ? {done}")
        if done.get("result").get("value"):
            self.tab.pause_behaviors()
