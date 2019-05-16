import asyncio
import logging
import ujson
from asyncio import AbstractEventLoop

import aioredis
import uvloop
from aioredis import Redis

from autobrowser import build_automation_config, LocalBrowserDiver, run_automation

try:
    uvloop.install()
except Exception:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

CHROME = "google-chrome-unstable"  # aka chrome canary

MAYBE_ADDITIONAL_ARGS = [
    "--disable-gpu-process-crash-limit",  # Disable the limit on the number of times the GPU process may be restarted. For tests and platforms where software fallback is disabled
    "--disable-backing-store-limit",
    "--aggressive",
    "--aggressive-cache-discard",
    "--aggressive-tab-discard",
    "--javascript-harmony",
    "--enable-features=NetworkService,NetworkServiceInProcess",
    "--enable-features=AwaitOptimization,brotli-encoding",
    "--bypass-app-banner-engagement-checks",
    "--disable-features=LazyFrameLoading",
]

# https://cs.chromium.org/chromium/src/chrome/browser/flag_descriptions.cc?q=kAggressiveThreshold&dr=CSs&l=3491
DEFAULT_ARGS = [
    "--remote-debugging-port=9222",
    "--disable-gpu-process-crash-limit",
    "--disable-backing-store-limit",
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
    "--disable-domain-reliability",
    "--disable-infobars",
    "--disable-features=site-per-process,TranslateUI,LazyFrameLoading",
    "--disable-breakpad",
    "--disable-backing-store-limit",
    "--enable-features=NetworkService,NetworkServiceInProcess,brotli-encoding,AwaitOptimization",
    "--metrics-recording-only",
    "--no-first-run",
    "--safebrowsing-disable-auto-update",
    "--mute-audio",
    "--autoplay-policy=no-user-gesture-required",
    "about:blank",
]


dummy_auto_id = "321"
info_key = f"a:{dummy_auto_id}:info"
scope_key = f"a:{dummy_auto_id}:scope"
seen_key = f"a:{dummy_auto_id}:seen"
done_key = f"{dummy_auto_id}:br:done"
q_key = f"a:{dummy_auto_id}:q"

default_seed_list = [
    "http://garden-club.link/",
    "https://www.iana.org/",
    "http://www.spiritsurfers.net/",
    "https://nodejs.org/dist/latest-v11.x/docs/api/",
    "https://www.instagram.com/rhizomedotorg",
    "https://www.youtube.com/watch?v=MfH0oirdHLs",
    "https://www.facebook.com/Smithsonian/",
    "https://twitter.com/hashtag/iipcwac18?vertical=default&src=hash",
    "https://soundcloud.com/perturbator",
    "https://www.slideshare.net/annaperricci?utm_campaign=profiletracking&utm_medium=sssite&utm_source=ssslideview",
    "https://twitter.com/webrecorder_io",
    "https://rhizome.org/",
]


async def reset_redis(
    redis: Redis, loop: AbstractEventLoop, hard: bool = False
) -> None:
    if hard:
        await redis.flushall()
    else:
        await redis.delete(q_key, info_key, seen_key, scope_key, done_key),
    await redis.hset(info_key, "crawl_depth", 2),
    for url in default_seed_list:
        await asyncio.gather(
            redis.rpush(q_key, ujson.dumps({"url": url, "depth": 0})),
            redis.sadd(seen_key, url),
            loop=loop,
        )
    # await redis.hset(info_key, "browser_overrides", ujson.dumps({
    #     "accept_language": "fr-CH, fr;q=0.9, en;q=0.8, de;q=0.7, *;q=0.5"
    # }))

RESET_REDIS = True
RESET_REDIS_HARD = True

logger = logging.getLogger("autobrowser")
logger.setLevel(logging.DEBUG)


async def crawl_baby_crawl() -> int:
    loop: AbstractEventLoop = asyncio.get_event_loop()
    if RESET_REDIS:
        redis: Redis = await aioredis.create_redis(
            "redis://localhost", loop=loop, encoding="utf-8"
        )
        await reset_redis(redis, loop, RESET_REDIS_HARD)
        redis.close()
        await redis.wait_closed()
    local_driver = LocalBrowserDiver(
        conf=build_automation_config(
            autoid=dummy_auto_id,
            reqid="abc321",
            chrome_opts={"launch": True, "exe": CHROME, "args": DEFAULT_ARGS},
            tab_type="CrawlerTab",
        ),
        loop=loop,
    )
    return await local_driver.run()


if __name__ == "__main__":
    run_automation(crawl_baby_crawl(), debug=True)
