from functools import wraps
from asyncio import AbstractEventLoop
from contextlib import asynccontextmanager
from functools import wraps
from typing import Dict, Optional, Callable, Coroutine, Any

from cripy import Client
from cripy import connect
from simplechrome.frame_manager import FrameManager

from .chrome import CHROME, launch_chrome, find_tab


@asynccontextmanager
async def cdp_client(
    chrome: str = CHROME, loop: Optional[AbstractEventLoop] = None
) -> Client:
    proc = await launch_chrome(chrome=chrome, loop=loop)
    the_tab: Dict[str, str] = await find_tab()
    raise_error = False
    em = None
    if the_tab is not None:
        _client = await connect(the_tab["webSocketDebuggerUrl"], loop=loop, remote=True)
        yield _client
        await _client.dispose()
    else:
        raise_error = True
        em = "Could not find a tab to connect to"
    proc.kill()
    if raise_error:
        raise Exception(em)


def cdp_client_runner(
    f: Callable[[Client], Coroutine[Any, Any, Any]]
) -> Callable[..., Coroutine[Any, Any, Any]]:
    @wraps(f)
    async def runner(*args, **kwargs) -> Any:
        async with cdp_client(*args, **kwargs) as client:
            return await f(client)

    return runner


async def create_frameman(client: Client) -> FrameManager:
    frame_tree = await client.Page.getFrameTree()
    return FrameManager(client, frame_tree["frameTree"], None)
