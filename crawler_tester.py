import asyncio
import traceback
import ujson
from asyncio import AbstractEventLoop
from contextlib import asynccontextmanager
from typing import Dict

import aioredis
import uvloop
from aioredis import Redis
from cripy import Client
import signal

from urlcanon import parse_url

from autobrowser.tabs.crawlerTab import CrawlerTab

# import sys
# logger = logging.getLogger('websockets')
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler(sys.stdout))
try:
    from asyncio.runners import run as aiorun
except ImportError:

    def aiorun(coro):
        loop = asyncio.get_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

CHROME = "google-chrome-unstable"  # aka chrome canary

DEFAULT_ARGS = [
    CHROME,
    "--remote-debugging-port=9222",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-client-side-phishing-detection",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-backgrounding-occluded-windows",
    "--disable-ipc-flooding-protection",
    "--disable-popup-blocking",
    "--disable-hang-monitor",
    "--disable-prompt-on-repost",
    "--disable-sync",
    "--disable-translate",
    "--disable-domain-reliability",
    "--disable-renderer-backgrounding",
    "--disable-infobars",
    "--disable-translate",
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
        *DEFAULT_ARGS, stderr=asyncio.subprocess.PIPE, loop=loop
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
    await redis.rpush(q_key, "https://twitter.com/webrecorder_io:0")
    await redis.sadd(seen_key, "https://twitter.com/webrecorder_io")
    await redis.sadd(
        scope_key,
        ujson.dumps(
            dict(
                type="surt",
                value=parse_url("https://twitter.com/")
                .surt(with_scheme=False)
                .decode("utf-8"),
            )
        ),
    )


RESET_REDIS = False


async def crawl_baby_crawl() -> None:
    loop: AbstractEventLoop = asyncio.get_event_loop()
    async with launch_chrome(loop) as tab_info:
        redis: Redis = await aioredis.create_redis(
            "redis://localhost", loop=loop, encoding="utf-8"
        )
        if RESET_REDIS:
            await reset_redis(redis)
        crawl_tab = None
        try:
            crawl_tab = CrawlerTab.create(None, tab_info, dummy_auto_id, redis=redis)
            await crawl_tab.init()
            await crawl_tab.crawl_loop
        except Exception as e:
            traceback.print_exc()
        finally:
            if crawl_tab:
                await crawl_tab.close()
            redis.close()
            await redis.wait_closed()


#

if __name__ == "__main__":
    aiorun(crawl_baby_crawl())
