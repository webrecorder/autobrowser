import asyncio
import ujson
from typing import Optional, List, Dict, Any, Union
import logging

import attr
from aiohttp import ClientSession

from autobrowser.errors import BrowserInitError

CDP_JSON: str = "http://{ip}:9222/json"
CDP_JSON_NEW: str = "http://{ip}:9222/json/new"
REQ_BROWSER_URL: str = "/request_browser/{browser}"
INIT_BROWSER_URL: str = "/init_browser?reqid={reqid}"
GET_BROWSER_INFO_URL: str = "/info/{reqid}"
WAIT_TIME: float = 0.5

logger = logging.getLogger("autobrowser")

__all__ = [
    "AutoRequests",
    "CDP_JSON",
    "CDP_JSON_NEW",
    "REQ_BROWSER_URL",
    "INIT_BROWSER_URL",
    "GET_BROWSER_INFO_URL",
    "WAIT_TIME",
]


@attr.dataclass(slots=True)
class AutoRequests(object):
    api_host: str = attr.ib(default="")
    base_ip_url: str = attr.ib(init=False, default=None)
    base_request_new_browser_url: str = attr.ib(init=False, default=None)
    base_init_browser_url: str = attr.ib(init=False, default=None)
    session: ClientSession = attr.ib(
        init=False, factory=lambda: ClientSession(json_serialize=ujson.dumps)
    )

    async def init_new_browser(
        self, browser_id: str, data: Optional[Any] = None
    ) -> Optional[Dict[str, Union[str, List[Dict[str, str]]]]]:
        reqid = self.stage_new_browser(browser_id, data)
        while True:
            response = await self.session.get(
                self.api_host + self.base_init_browser_url.format(reqid=reqid),
                headers=dict(Host="localhost"),
            )
            data = await response.json()
            if "cmd_port" in data:
                break
            logger.info("Waiting for Browser: " + str(data))
            await asyncio.sleep(WAIT_TIME)
        tab_datas = await self.wait_for_tabs(data.get("ip"))
        return dict(ip=data.get("ip"), reqid=reqid, tab_datas=tab_datas)

    async def stage_new_browser(
        self, browser_id: str, data: Optional[Any] = None
    ) -> str:
        response = await self.session.post(
            self.base_request_new_browser_url.format(browser=browser_id), data=data
        )
        json = await response.json()
        reqid = json.get("reqid")
        if reqid is None:
            raise BrowserInitError(f"Could not stage browser with id = {browser_id}")
        return reqid

    async def wait_for_tabs(self, ip: str) -> List[Dict[str, str]]:
        while True:
            tab_datas = await self.find_browser_tabs(ip=ip)
            if tab_datas:
                return tab_datas
            logger.debug("Waiting for first tab")
            await asyncio.sleep(WAIT_TIME)

    async def find_browser_tabs(
        self,
        ip: Optional[str] = None,
        url: Optional[str] = None,
        require_ws: Optional[bool] = True,
    ) -> List[Dict[str, str]]:
        res = await self.session.get(CDP_JSON.format(ip=ip))
        tabs = await res.json()
        filtered_tabs: List[Dict[str, str]] = []

        for tab in tabs:
            logger.debug("Tab: " + str(tab))

            if require_ws and "webSocketDebuggerUrl" not in tab:
                continue

            if tab.get("type") == "page" and (not url or url == tab["url"]):
                filtered_tabs.append(tab)

        return filtered_tabs

    async def get_ip_for_reqid(self, reqid: str) -> Optional[str]:
        """Retrieve the ip address associated with a requests id

        :param reqid: The request id to retrieve the ip address for
        :return: The ip address associated with the request id if it exists
        """
        logger.info(f"AutoRequests[get_ip_for_reqid]: reqid = {reqid}")
        res = await self.session.get(self.base_ip_url.format(reqid=reqid))
        json = await res.json()
        return json.get("ip")

    async def create_browser_tab(self, ip: str) -> Dict[str, str]:
        res = await self.session.get(CDP_JSON_NEW.format(ip=ip))
        return await res.json()

    async def close(self):
        await self.session.close()

    def __attrs_post_init__(self) -> None:
        self.base_ip_url = self.api_host + GET_BROWSER_INFO_URL
        self.base_request_new_browser_url = self.api_host + REQ_BROWSER_URL
        self.base_init_browser_url = self.api_host + INIT_BROWSER_URL