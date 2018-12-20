import asyncio
import logging
import traceback
import ujson
from asyncio import AbstractEventLoop

import aioredis
import uvloop
from aioredis import Redis

from autobrowser import build_automation_config, LocalBrowserDiver, run_automation

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
        ujson.dumps(dict(url="https://www.youtube.com/watch?v=MfH0oirdHLs", depth=0)),
        ujson.dumps(dict(url="https://www.facebook.com/Smithsonian/", depth=0)),
        ujson.dumps(dict(url="https://www.instagram.com/rhizomedotorg", depth=0)),
        ujson.dumps(
            dict(
                url="https://twitter.com/hashtag/iipcwac18?vertical=default&src=hash",
                depth=0,
            )
        ),
        ujson.dumps(dict(url="https://soundcloud.com/perturbator", depth=0)),
        ujson.dumps(
            dict(
                url="https://www.slideshare.net/annaperricci?utm_campaign=profiletracking&utm_medium=sssite&utm_source=ssslideview",
                depth=0,
            )
        ),
        ujson.dumps(dict(url="https://twitter.com/webrecorder_io", depth=0)),
        # ujson.dumps(dict(url="https://rhizome.org/", depth=0)),
    )
    await redis.sadd(seen_key, "https://www.youtube.com/watch?v=MfH0oirdHLs")
    await redis.sadd(seen_key, "https://www.facebook.com/Smithsonian/")
    await redis.sadd(seen_key, "https://soundcloud.com/perturbator")
    await redis.sadd(seen_key, "https://twitter.com/webrecorder_io")
    await redis.sadd(
        seen_key,
        "https://twitter.com/hashtag/iipcwac18?f=tweets&vertical=default&src=hash",
    )
    await redis.sadd(
        seen_key,
        "https://www.slideshare.net/annaperricci?utm_campaign=profiletracking&utm_medium=sssite&utm_source=ssslideview",
    )
    await redis.sadd(seen_key, "https://www.instagram.com/rhizomedotorg")
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


async def crawl_baby_crawl() -> int:
    loop: AbstractEventLoop = asyncio.get_event_loop()
    local_driver: LocalBrowserDiver = None
    if RESET_REDIS:
        redis: Redis = await aioredis.create_redis(
            "redis://localhost", loop=loop, encoding="utf-8"
        )
        await reset_redis(redis)
        redis.close()
        await redis.wait_closed()
    try:
        local_driver = LocalBrowserDiver(
            conf=build_automation_config(
                autoid=dummy_auto_id,
                chrome_opts=dict(launch=True, exe=CHROME, args=DEFAULT_ARGS),
                tab_type="CrawlerTab",
            ),
            loop=loop,
        )

        return await local_driver.run()
    finally:
        if local_driver:
            return await local_driver.shutdown()


if __name__ == "__main__":
    run_automation(crawl_baby_crawl())
