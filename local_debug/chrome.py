import asyncio
from asyncio import AbstractEventLoop
from asyncio.subprocess import Process
from contextlib import asynccontextmanager
from functools import wraps
from typing import Dict, Optional, Callable, Coroutine, Any

from cripy import Client

CHROME = "google-chrome-unstable"  # aka chrome canary

DEFAULT_ARGS = [
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


async def launch_chrome(
    chrome: str = CHROME, loop: Optional[AbstractEventLoop] = None
) -> Process:
    proc = await asyncio.create_subprocess_exec(
        chrome,
        *DEFAULT_ARGS,
        stderr=asyncio.subprocess.PIPE,
        loop=loop if loop is not None else asyncio.get_event_loop(),
    )
    while True:
        line = await proc.stderr.readline()
        if b"DevTools listening on" in line:
            print(f"{line}")
            break
    return proc


async def find_tab() -> Optional[Dict[str, str]]:
    for tab in await Client.List():
        if tab["type"] == "page":
            return tab
    return None


@asynccontextmanager
async def chrome_tab(
    chrome: str = CHROME, loop: Optional[AbstractEventLoop] = None
) -> Dict[str, str]:
    proc = await launch_chrome(chrome=chrome, loop=loop)
    yield await find_tab()
    proc.kill()


def chrome_tab_runner(
    f: Callable[[Dict[str, str]], Coroutine[Any, Any, Any]]
) -> Callable[..., Coroutine[Any, Any, Any]]:
    @wraps(f)
    async def runner(*args, **kwargs) -> Any:
        async with chrome_tab(*args, **kwargs) as tab_data:
            return await f(tab_data)

    return runner

