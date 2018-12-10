from typing import Dict, Optional
import attr
import os

__all__ = ["AutomationInfo"]


@attr.dataclass(slots=True)
class AutomationInfo(object):
    """A class containing all the information pertaining to the running automation"""
    #: Which tab class is to be used
    tab_type: str = attr.ib(default="BehaviorTab", repr=False)
    #: Which browser should be requested if a new one is to be used
    browser_id: str = attr.ib(default="chrome:67", repr=False)
    #: How many tabs should a browser control
    num_tabs: int = attr.ib(default=1, repr=False)
    #: Adtional options to be supplied to a tab
    tab_opts: Dict = attr.ib(factory=dict, repr=False)
    pubsub: bool = attr.ib(default=False, repr=False)
    cdata: Optional[Dict] = attr.ib(default=None, repr=False)
    #: The id for this running automation
    autoid: str = attr.ib(default=None)
    #: The id for the request made to shepard
    reqid: str = attr.ib(default=None)
    #: The ip of the browser we are connecting to
    ip: str = attr.ib(default=None)
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

