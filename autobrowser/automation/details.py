import socket
from typing import Dict, Optional, Any, List
import attr
import os
import ujson

__all__ = ["AutomationInfo", "AutomationConfig", "build_automation_config"]


def get_browser_host_ip(browser_host: Optional[str]) -> str:
    if browser_host is not None:
        return socket.gethostbyname(browser_host)
    return ""


AutomationConfig = Dict[str, Any]


def build_automation_config(
    options: Optional[Dict] = None, **kwargs: Any
) -> AutomationConfig:
    browser_host = os.environ.get("BROWSER_HOST")
    chrome_opts = ujson.loads(os.environ.get('CHROME_OPTS')) if "CHROME_OPTS" in os.environ else None
    conf: AutomationConfig = dict(
        redis_url=os.environ.get("REDIS_URL", "redis://localhost"),
        tab_type=os.environ.get("TAB_TYPE", "BehaviorTab"),
        browser_id=os.environ.get("BROWSER_ID", "chrome:67"),
        browser_host=browser_host,
        browser_host_ip=get_browser_host_ip(browser_host),
        api_host=os.environ.get("SHEPARD_HOST", "http://shepherd:9020"),
        num_tabs=int(os.environ.get("NUM_TABS", 1)),
        autoid=os.environ.get("AUTO_ID"),
        chrome_opts=chrome_opts,
        max_behavior_time=int(os.environ.get("BEHAVIOR_RUN_TIME", 60)),
        navigation_timeout=int(os.environ.get("NAV_TO", 60)),
        net_cache_disabled=bool(os.environ.get("CRAWL_NO_NETCACHE")),
        wait_for_q=bool(os.environ.get("WAIT_FOR_Q")),
    )

    if options is not None:
        conf.update(options)

    conf.update(kwargs)

    return conf


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
