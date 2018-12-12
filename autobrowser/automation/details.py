import socket
from typing import Dict, Optional
import attr
import os

__all__ = ["AutomationInfo", "AutomationConfig"]


def get_browser_host_ip() -> str:
    bhost = os.environ.get("BROWSER_HOST")
    if bhost is not None:
        return socket.gethostbyname(bhost)
    return ""


@attr.dataclass(slots=True)
class AutomationConfig(object):
    #: Which tab class is to be used
    tab_type: str = attr.ib(
        default=os.environ.get("TAB_TYPE", "BehaviorTab"), repr=False
    )
    #: Which browser should be requested if a new one is to be used
    browser_id: str = attr.ib(
        default=os.environ.get("BROWSER_ID", "chrome:67"), repr=False
    )
    #: The ip of the browser we are connecting to
    browser_host_ip: str = attr.ib(factory=get_browser_host_ip, repr=False)
    api_host: str = attr.ib(
        default=os.environ.get("SHEPARD_HOST", "http://shepherd:9020")
    )
    #: How many tabs should a browser control
    num_tabs: int = attr.ib(default=int(os.environ.get("NUM_TABS", 1)), repr=False)
    #: The id for this running automation
    autoid: Optional[str] = attr.ib(default=os.environ.get("AUTO_ID"))
    #: Adtional options to be supplied to a tab
    tab_opts: Dict = attr.ib(factory=dict, repr=False)
    cdata: Optional[Dict] = attr.ib(default=None, repr=False)


@attr.dataclass(slots=True)
class AutomationInfo(object):
    """A class containing all the information pertaining to the running automation
    as far as browsers and tabs are concerned
    """
    #: Which tab class is to be used
    tab_type: str = attr.ib(
        default=os.environ.get("TAB_TYPE", "BehaviorTab"), repr=False
    )
    #: The id for this running automation
    autoid: Optional[str] = attr.ib(default=None)
    #: The id for the request made to shepard
    reqid: Optional[str] = attr.ib(default=None)
    max_behavior_time: int = attr.ib(
        default=int(os.environ.get("BEHAVIOR_RUN_TIME", 60)), repr=False
    )
    navigation_timeout: int = attr.ib(
        default=int(os.environ.get("NAV_TO", 60)), repr=False
    )
    net_cache_disabled: bool = attr.ib(
        default=bool(os.environ.get("CRAWL_NO_NETCACHE")), repr=False
    )
    wait_for_q: bool = attr.ib(default=bool(os.environ.get("WAIT_FOR_Q")), repr=False)
