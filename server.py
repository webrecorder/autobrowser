# fmt: off
from better_exceptions import hook as be_hook; be_hook()
# fmt: on
import asyncio
from pathlib import Path
from typing import Dict
import aiohttp_jinja2
import jinja2
import uvloop
from functools import partial
from aiohttp import AsyncResolver, ClientSession, TCPConnector
from aiohttp.web import Application, Request, Response, RouteTableDef, run_app
from aiojobs.aiohttp import atomic, setup as aiojhttp_setup
from ujson import dumps as ujson_dumps


try:
    uvloop.install()
except Exception:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

routes = RouteTableDef()

ROOT_PATH = Path(__file__).parent
SHEPHERD_HOST = "http://shepherd:9020"
SHEPHERD_START = f"{SHEPHERD_HOST}/api/behavior/start/"
SHEPHERD_STOP = f"{SHEPHERD_HOST}/api/behavior/stop/"


async def http_session(app: Application) -> None:
    loop = asyncio.get_event_loop()
    app["autob_http_session"] = ClientSession(
        connector=TCPConnector(resolver=AsyncResolver(loop=loop), loop=loop),
        json_serialize=partial(ujson_dumps, ensure_ascii=False),
        loop=loop,
    )
    yield
    await app["autob_http_session"].close()


@routes.get("/view/{url:.+}")
@aiohttp_jinja2.template("autobrowser.html")
async def autobrowser_view(request: Request) -> Dict:
    return {"url": request.match_info["url"], "browser": "chrome:67"}


@routes.get("/api/autostart/{requid}")
@atomic
async def trigger_auto_start(request: Request) -> Response:
    reqid = request.match_info["requid"]
    session: ClientSession = request.app.get("autob_http_session")
    async with session.post(f"{SHEPHERD_START}{reqid}") as res:
        return Response(body=await res.read(), status=res.status, headers=res.headers)


@routes.get("/api/autostop/{requid}")
@atomic
async def trigger_auto_stop(request: Request) -> Response:
    reqid = request.match_info["requid"]
    session: ClientSession = request.app.get("autob_http_session")
    async with session.post(f"{SHEPHERD_STOP}{reqid}") as res:
        return Response(body=await res.read(), status=res.status, headers=res.headers)


async def init() -> Application:
    app = Application(client_max_size=1024 ** 4)
    aiojhttp_setup(app)
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(str(ROOT_PATH / "templates"))
    )
    routes.static("/static", str(ROOT_PATH / "static"))
    app.add_routes(routes)
    app.cleanup_ctx.append(http_session)
    return app


if __name__ == "__main__":
    run_app(init(), host="0.0.0.0", port=9021)
