import socket
from typing import Any, Counter as CounterT, Dict, List, Optional, TYPE_CHECKING
from collections import Counter
from enum import Enum, auto
import attr
import os
import ujson


if TYPE_CHECKING:
    from autobrowser.abcs import BehaviorManager

__all__ = [
    "AutomationConfig",
    "AutomationInfo",
    "BrowserExitInfo",
    "CloseReason",
    "RedisKeys",
    "TabClosedInfo",
    "build_automation_config",
    "exit_code_from_reason",
]


def get_browser_host_ip(browser_host: Optional[str]) -> str:
    if browser_host is not None:
        return socket.gethostbyname(browser_host)
    return ""


AutomationConfig = Dict[str, Any]


def build_automation_config(
    options: Optional[Dict] = None, **kwargs: Any
) -> AutomationConfig:
    browser_host = os.environ.get("BROWSER_HOST")
    chrome_opts = (
        ujson.loads(os.environ.get("CHROME_OPTS"))
        if "CHROME_OPTS" in os.environ
        else None
    )
    conf: AutomationConfig = dict(
        redis_url=os.environ.get("REDIS_URL", "redis://localhost"),
        tab_type=os.environ.get("TAB_TYPE", "BehaviorTab"),
        browser_id=os.environ.get("BROWSER_ID", "chrome:67"),
        browser_host=browser_host,
        browser_host_ip=get_browser_host_ip(browser_host),
        api_host=os.environ.get("SHEPARD_HOST", "http://shepherd:9020"),
        num_tabs=int(os.environ.get("NUM_TABS", 1)),
        autoid=os.environ.get("AUTO_ID"),
        reqid=os.environ.get("REQ_ID"),
        chrome_opts=chrome_opts,
        max_behavior_time=int(os.environ.get("BEHAVIOR_RUN_TIME", 60)),
        navigation_timeout=int(os.environ.get("NAV_TO", 30)),
        net_cache_disabled=bool(os.environ.get("CRAWL_NO_NETCACHE")),
        wait_for_q=int(os.environ.get("WAIT_FOR_Q", 0)),
        behavior_api_url=os.environ.get("BEHAVIOR_API_URL", "http://localhost:3030"),
        fetch_behavior_endpoint=os.environ.get(
            "FETCH_BEHAVIOR_ENDPOINT", "http://localhost:3030/behavior?url="
        ),
        fetch_behavior_info_endpoint=os.environ.get(
            "FETCH_BEHAVIOR_INFO_ENDPOINT", "http://localhost:3030/info?url="
        ),
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

    behavior_manager: "BehaviorManager" = attr.ib()

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
        default=int(os.environ.get("NAV_TO", 30)), repr=False
    )
    net_cache_disabled: bool = attr.ib(
        default=bool(os.environ.get("CRAWL_NO_NETCACHE")), repr=False
    )
    wait_for_q: int = attr.ib(default=int(os.environ.get("WAIT_FOR_Q", 0)), repr=False)


def to_redis_key(aid: str) -> str:
    return f"a:{aid}"


@attr.dataclass(slots=True)
class RedisKeys(object):
    """Utility class that has the redis keys used by an automation as properties"""

    autoid: str = attr.ib(converter=to_redis_key)
    info: str = attr.ib(init=False, default=None)
    queue: str = attr.ib(init=False, default=None)
    pending: str = attr.ib(init=False, default=None)
    seen: str = attr.ib(init=False, default=None)
    scope: str = attr.ib(init=False, default=None)
    auto_done: str = attr.ib(init=False, default=None)

    def __attrs_post_init__(self) -> None:
        self.info = f"{self.autoid}:info"
        self.queue = f"{self.autoid}:q"
        self.pending = f"{self.autoid}:qp"
        self.seen = f"{self.autoid}:seen"
        self.scope = f"{self.autoid}:scope"
        self.auto_done = f"{self.autoid}:br:done"


class CloseReason(Enum):
    """An enumeration of the possible reasons for a tab to become closed"""

    GRACEFULLY = auto()
    CONNECTION_CLOSED = auto()
    TARGET_CRASHED = auto()
    CLOSED = auto()
    CRAWL_END = auto()
    NONE = auto()

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.__str__()


def exit_code_from_reason(reason: CloseReason) -> int:
    if reason in (CloseReason.TARGET_CRASHED, CloseReason.CONNECTION_CLOSED):
        return 2
    return 0


@attr.dataclass(slots=True)
class TabClosedInfo(object):
    """Simple data class containing the information about why a tab closed"""

    tab_id: str = attr.ib()
    reason: CloseReason = attr.ib()


@attr.dataclass(slots=True)
class BrowserExitInfo(object):
    """Simple data class containing the information about why a browser is exiting"""

    auto_info: AutomationInfo = attr.ib()
    tab_closed_reasons: List[TabClosedInfo] = attr.ib()

    def exit_reason_code(self) -> int:
        tcr_len = len(self.tab_closed_reasons)
        if tcr_len == 0:
            return 0
        elif tcr_len == 1:
            return exit_code_from_reason(self.tab_closed_reasons[0].reason)
        tcr_counter: CounterT[CloseReason] = Counter()
        for tcr in self.tab_closed_reasons:
            tcr_counter[tcr.reason] += 1
        exit_reason, count = max(
            tcr_counter.items(), key=lambda reason_count: reason_count[1]
        )
        return exit_code_from_reason(exit_reason)
