import asyncio
import logging
import sys
import traceback
import ujson
from asyncio import AbstractEventLoop
from contextlib import asynccontextmanager
from typing import Dict, List

import aioredis
import uvloop
from aioredis import Redis
from cripy import Client
from urlcanon import parse_url

from autobrowser.tabs.crawlerTab import CrawlerTab

# import sys

try:
    from asyncio.runners import run as aiorun
except ImportError:

    def aiorun(coro, debug=False) -> None:
        loop = asyncio.get_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

CHROME = "google-chrome-unstable"  # aka chrome canary

MAYBE_ADDITIONAL_ARGS = [
    "--disable-gpu-process-crash-limit",  # Disable the limit on the number of times the GPU process may be restarted. For tests and platforms where software fallback is disabled
    "--disable-backing-store-limit",
    "--aggressive",
    "--aggressive-cache-discard",
    "--aggressive-tab-discard",
    "--javascript-harmony",
]

# https://cs.chromium.org/chromium/src/chrome/browser/flag_descriptions.cc?q=kAggressiveThreshold&dr=CSs&l=3491
DEFAULT_ARGS = [
    "--remote-debugging-port=9222",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-ipc-flooding-protection",
    "--disable-client-side-phishing-detection",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-popup-blocking",
    "--disable-hang-monitor",
    "--disable-prompt-on-repost",
    "--disable-sync",
    "--disable-translate",
    "--disable-domain-reliability",
    "--disable-infobars",
    "--disable-features=site-per-process",
    "--disable-breakpad",
    "--metrics-recording-only",
    "--no-first-run",
    "--safebrowsing-disable-auto-update",
    "--password-store=basic",
    "--use-mock-keychain",
    "--mute-audio",
    "--autoplay-policy=no-user-gesture-required",
    "about:blank",
]


@asynccontextmanager
async def launch_chrome(loop: AbstractEventLoop) -> Dict[str, str]:
    proc = await asyncio.create_subprocess_exec(
        CHROME,
        *DEFAULT_ARGS,
        stderr=asyncio.subprocess.PIPE,
        loop=loop,
    )
    while True:
        line = await proc.stderr.readline()
        if b"DevTools listening on" in line:
            print(f"{line}")
            break
    the_tab: Dict[str, str] = None
    for tab in await Client.List():
        if tab["type"] == "page":
            the_tab = tab
    if the_tab is not None:
        yield the_tab
    proc.terminate()
    await proc.wait()


dummy_auto_id = "123"
info_key = f"a:{dummy_auto_id}:info"
scope_key = f"a:{dummy_auto_id}:scope"
seen_key = f"a:{dummy_auto_id}:seen"
q_key = f"a:{dummy_auto_id}:q"


async def reset_redis(redis: Redis):
    await redis.delete(q_key, info_key, seen_key, scope_key)
    await redis.hset(info_key, "crawl_depth", 2)
    await redis.rpush(
        q_key,
        ujson.dumps(dict(url="https://www.youtube.com/watch?v=Oi0sVRZ_49c", depth=0)),
        # ujson.dumps(dict(url="https://www.instagram.com/rhizomedotorg", depth=0)),
        # ujson.dumps(dict(url="https://rhizome.org/", depth=0)),
    )
    await redis.sadd(seen_key, "https://www.youtube.com/watch?v=Oi0sVRZ_49c")
    # await redis.sadd(seen_key, "https://www.instagram.com/rhizomedotorg")
    # await redis.sadd(seen_key, "https://rhizome.org/")
    # await redis.sadd(
    #     scope_key,
    #     ujson.dumps(
    #         dict(surt=parse_url("https://twitter.com/").surt().decode("utf-8"))
    #     ),
    # )


RESET_REDIS = True

logger = logging.getLogger("autobrowser")
logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler(sys.stdout))


async def crawl_baby_crawl() -> None:
    loop: AbstractEventLoop = asyncio.get_event_loop()
    async with launch_chrome(loop) as tab_info:
        crawl_tab: CrawlerTab = None
        redis: Redis = None
        try:
            redis: Redis = await aioredis.create_redis(
                "redis://localhost", loop=loop, encoding="utf-8"
            )
            if RESET_REDIS:
                await reset_redis(redis)
            crawl_tab = CrawlerTab.create(None, tab_info, dummy_auto_id, redis=redis)
            await crawl_tab.init()
            await crawl_tab.crawl_loop
        except Exception as e:
            traceback.print_exc()
        finally:
            if crawl_tab:
                await crawl_tab.close()
            if redis:
                redis.close()
                await redis.wait_closed()


#

if __name__ == "__main__":
    aiorun(crawl_baby_crawl())
