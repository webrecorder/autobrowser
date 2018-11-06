import asyncio
from asyncio import AbstractEventLoop
from typing import List, Dict
import traceback

from cripy import Client, connect
from contextlib import asynccontextmanager
from async_timeout import timeout
import uvloop
import logging
from autobrowser.tabs.crawlerTab import CrawlerTab
from urlcanon import parse_url
# import sys
# logger = logging.getLogger('websockets')
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler(sys.stdout))
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
    proc.kill()


async def crawl_baby_crawl(loop: AbstractEventLoop) -> None:
    async with launch_chrome(loop) as tab_info:
        crawl_tab = None
        try:
            crawl_tab = CrawlerTab.create(
                None,
                tab_info,
                frontier=dict(depth=2, seed_list=["https://twitter.com/AnnaPerricci/status/1055500045930414085"]),
            )
            await crawl_tab.init()
            await crawl_tab.crawl_loop
        except Exception as e:
            traceback.print_exc()
        if crawl_tab:
            await crawl_tab.close()
#

if __name__ == "__main__":
    # _loop = asyncio.get_event_loop()
    # _loop.run_until_complete(crawl_baby_crawl(_loop))
    import ujson
    with open('frontier.json', 'r') as iin:
        f = ujson.load(iin)
    for it in f:
        print(parse_url(it).surt(with_scheme=False))

