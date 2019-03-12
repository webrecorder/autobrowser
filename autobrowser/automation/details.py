from collections import Counter
from enum import Enum, auto
from os import environ as os_environ
from socket import gethostbyname as socket_gethostbyname
from typing import (
    Any,
    Counter as CounterT,
    Dict,
    List,
    Optional,
    TYPE_CHECKING,
    Type,
    Union,
)
from ujson import loads as ujson_loads

from attr import dataclass as attr_dataclass, ib as attr_ib

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


def get_browser_host_ip(browser_host: Optional[str] = None) -> str:
    if browser_host is not None:
        return socket_gethostbyname(browser_host)
    return ""


def env(
    key: str,
    type_: Type[Union[str, bool, int, dict]] = str,
    default: Optional[Any] = None,
) -> Union[str, int, bool, Dict]:
    if key not in os_environ:
        return default

    val = os_environ[key]

    if type_ == str:
        return val
    elif type_ == bool:
        if val.lower() in ["1", "true", "yes", "y", "ok", "on"]:
            return True
        if val.lower() in ["0", "false", "no", "n", "nok", "off"]:
            return False
        raise ValueError(
            f"Invalid environment variable '{key}' (expected a boolean): '{val}'"
        )
    elif type_ == int:
        try:
            return int(val)
        except ValueError:
            raise ValueError(
                f"Invalid environment variable '{key}' (expected ab integer): '{val}'"
            )
    elif type_ == dict:
        return ujson_loads(val)


AutomationConfig = Dict[str, Any]


def build_automation_config(
    options: Optional[Dict] = None, **kwargs: Any
) -> AutomationConfig:
    browser_host = env("BROWSER_HOST")
    behavior_api_url = env("BEHAVIOR_API_URL", default="http://localhost:3030")
    conf: AutomationConfig = dict(
        redis_url=env("REDIS_URL", default="redis://localhost"),
        tab_type=env("TAB_TYPE", default="BehaviorTab"),
        browser_id=env("BROWSER_ID", default="chrome:67"),
        browser_host=browser_host,
        browser_host_ip=get_browser_host_ip(browser_host),
        api_host=env("SHEPARD_HOST", default="http://shepherd:9020"),
        num_tabs=env("NUM_TABS", type_=int, default=1),
        autoid=env("AUTO_ID"),
        reqid=env("REQ_ID"),
        chrome_opts=env("CHROME_OPTS", type_=dict),
        max_behavior_time=env("BEHAVIOR_RUN_TIME", type_=int, default=60),
        navigation_timeout=env("NAV_TO", type_=int, default=30),
        net_cache_disabled=env("CRAWL_NO_NETCACHE", type_=bool, default=True),
        wait_for_q=env("WAIT_FOR_Q", type_=bool, default=True),
        behavior_api_url=behavior_api_url,
        fetch_behavior_endpoint=env(
            "FETCH_BEHAVIOR_ENDPOINT", default=f"{behavior_api_url}/behavior?url="
        ),
        fetch_behavior_info_endpoint=env(
            "FETCH_BEHAVIOR_INFO_ENDPOINT", default=f"{behavior_api_url}/info?url="
        ),
    )

    if options is not None:
        conf.update(options)

    conf.update(kwargs)

    return conf


@attr_dataclass(slots=True)
class AutomationInfo(object):
    """A class containing all the information pertaining to the running automation
    as far as browsers and tabs are concerned
    """

    behavior_manager: "BehaviorManager" = attr_ib()

    #: Which tab class is to be used
    tab_type: str = attr_ib(default=env("TAB_TYPE", default="BehaviorTab"), repr=False)
    #: The id for this running automation
    autoid: Optional[str] = attr_ib(default=None)
    #: The id for the request made to shepard
    reqid: Optional[str] = attr_ib(default=None)
    max_behavior_time: int = attr_ib(
        default=env("BEHAVIOR_RUN_TIME", type_=int, default=60), repr=False
    )
    navigation_timeout: int = attr_ib(
        default=env("NAV_TO", type_=int, default=30), repr=False
    )
    net_cache_disabled: bool = attr_ib(
        default=env("CRAWL_NO_NETCACHE", type_=bool, default=True), repr=False
    )
    wait_for_q: int = attr_ib(
        default=env("WAIT_FOR_Q", type_=bool, default=True), repr=False
    )


def to_redis_key(aid: str) -> str:
    return f"a:{aid}"


@attr_dataclass(slots=True)
class RedisKeys(object):
    """Utility class that has the redis keys used by an automation as properties"""

    autoid: str = attr_ib(converter=to_redis_key)
    info: str = attr_ib(init=False, default=None)
    queue: str = attr_ib(init=False, default=None)
    pending: str = attr_ib(init=False, default=None)
    seen: str = attr_ib(init=False, default=None)
    scope: str = attr_ib(init=False, default=None)
    auto_done: str = attr_ib(init=False, default=None)

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


@attr_dataclass(slots=True)
class TabClosedInfo(object):
    """Simple data class containing the information about why a tab closed"""

    tab_id: str = attr_ib()
    reason: CloseReason = attr_ib()


@attr_dataclass(slots=True)
class BrowserExitInfo(object):
    """Simple data class containing the information about why a browser is exiting"""

    auto_info: AutomationInfo = attr_ib()
    tab_closed_reasons: List[TabClosedInfo] = attr_ib()

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
