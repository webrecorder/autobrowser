import socket
import logging
from collections import Counter
from enum import Enum, auto
from os import environ
from typing import Any, Counter as CounterT, Dict, List, Optional, Type, Union
from ujson import loads as ujson_loads

from attr import dataclass as attr_dataclass, ib as attr_ib

__all__ = [
    "AutomationConfig",
    "BrowserExitInfo",
    "CloseReason",
    "RedisKeys",
    "TabClosedInfo",
    "build_automation_config",
    "exit_code_from_reason",
]

logger = logging.getLogger("autobrowser")


def get_browser_host_ip(browser_host: Optional[str] = None) -> Optional[str]:
    if browser_host is not None:
        return socket.gethostbyname(browser_host)
    return None


def env(
    key: str,
    type_: Type[Union[str, bool, int, dict]] = str,
    default: Optional[Any] = None,
) -> Union[str, int, bool, Dict]:
    """Returns the value of the supplied env key name converting
    the env key's value to the specified type.

    If the env key does not exist the default value is returned.

    Boolean values for env keys are expected to be:
      - true: 1, true, yes, y, ok, on
      - false: 0, false, no, n, nok, off

    :param key: The name of the environment variable
    :param type_: What type should the the env key's value be converted to,
    defaults to str
    :param default: The default value of the env key, defaults to None
    :return: The value of the env key or the supplied default
    """
    if key not in environ:
        return default

    val = environ[key]

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


@attr_dataclass(slots=True)
class AutomationConfig:
    """The AutomationConfig class is the single source of truth for details
    concerning the running automation.
    This class should be created, 99.9% of the time, by build_automation_config.
    """

    # configuration details concerning running an automation
    autoid: Optional[str] = attr_ib(default=None)
    reqid: Optional[str] = attr_ib(default=None)
    browser_id: str = attr_ib(default=None)
    num_tabs: int = attr_ib(default=None)
    tab_type: str = attr_ib(default=None)
    max_behavior_time: int = attr_ib(default=60)
    navigation_timeout: int = attr_ib(default=30)
    net_cache_disabled: bool = attr_ib(default=True)
    wait_for_q: int = attr_ib(default=True)

    # configuration details concerning redis
    redis_url: str = attr_ib(default=None)

    # configuration details concerning behaviors
    behavior_api_url: str = attr_ib(default=None)
    fetch_behavior_endpoint: str = attr_ib(default=None)
    fetch_behavior_info_endpoint: str = attr_ib(default=None)
    behavior_action_expression: str = attr_ib(default=None)
    behavior_paused_expression: str = attr_ib(default=None)
    page_url_expression: str = attr_ib(default=None)
    outlinks_expression: str = attr_ib(default=None)
    clear_outlinks_expression: str = attr_ib(default=None)
    no_out_links_express: str = attr_ib(default=None)

    # configuration details concerning shepherd
    shepherd_host: str = attr_ib(default=None)
    browser_host: str = attr_ib(default=None)
    browser_host_ip: str = attr_ib(default=None)
    req_browser_path: str = attr_ib(default=None)
    init_browser_pathq: str = attr_ib(default=None)
    browser_info_path: str = attr_ib(default=None)
    cdp_port: str = attr_ib(default=None)

    # configuration details concerning where to send screenshots
    # to if we are taking them
    screenshot_api_url: Optional[str] = attr_ib(default=None)
    screenshot_target_uri: Optional[str] = attr_ib(default=None)
    screenshot_format: Optional[str] = attr_ib(default=None)

    # other configuration details
    chrome_opts: Optional[Dict] = attr_ib(default=None, repr=False)
    additional_configuration: Optional[Dict] = attr_ib(default=None)

    @property
    def should_take_screenshot(self) -> bool:
        """Returns T/F indicating if an automation should
        take screenshots of pages and send them to the configured
        endpoint
        """
        return self.screenshot_api_url is not None

    def make_shepherd_url(self, shepherd_endpoint: str = "") -> str:
        """Creates a full shepherd end point URL using the supplied
        endpoint URL

        :param shepherd_endpoint: An shepherd endpoint
        :return: The full shepherd endpoint url
        """
        return f"{self.shepherd_host}{shepherd_endpoint}"

    def request_new_browser_url(self, browser_id: str) -> str:
        """Creates the full shepherd request new browser endpoint URL
        using the supplied browser id

        :param browser_id: The id of the new browser to be requested
        :return: The full url for requesting a new browser
        """
        return self.make_shepherd_url(f"{self.req_browser_path}{browser_id}")

    def browser_info_url(self, reqid: str) -> str:
        """Creates the full shepherd browser info endpoint URL using
        supplied request id with the configured

        :param reqid: The request id of the running automation
        :return: The full browser info url
        """
        return self.make_shepherd_url(f"{self.browser_info_path}{reqid}")

    def init_browser_url(self, reqid: str) -> str:
        """Creates full shepard initializing a new browser endpoint URL
        using the supplied automation's request id

        :param reqid: The request id of the running automation
        :return: The full init new browser url
        """
        return self.make_shepherd_url(f"{self.init_browser_pathq}{reqid}")

    def make_cdp_url(self, browser_ip_or_host: str) -> str:
        """Creates the base CDP url using the supplied browser ip address or
        hostname with the configured cdp port

        :param browser_ip_or_host: An browsers ip address or hostname
        :return: The base CDP url to be used for communicating with the browser
        """
        return f"http://{browser_ip_or_host}:{self.cdp_port}"

    def cdp_json_url(self, browser_ip_or_host: str) -> str:
        """Creates the CDP url for the /json endpoint using the supplied browser
        ip address or hostname

        :param browser_ip_or_host: An browsers ip address or hostname
        :return: The full CDP /json endpoint url of the browser
        """
        return f"{self.make_cdp_url(browser_ip_or_host)}/json"

    def cdp_json_new_url(self, browser_ip_or_host: str) -> str:
        """Creates the CDP url for the /json endpoint using the supplied browser
        ip address or hostname

        :param browser_ip_or_host: An browsers ip address or hostname
        :return: The full CDP /json endpoint url of the browser
        """
        return f"{self.make_cdp_url(browser_ip_or_host)}/json/new"

    def retrieve_behavior_url(self, page_url: str) -> str:
        """Creates the full URL to be used for retrial of a behavior
        using the supplied page url

        :param page_url: The URL of the page to retrieve a behavior for
        :return: The full fetch behavior for a page endpoint URL
        """
        return f"{self.fetch_behavior_endpoint}{page_url}"

    def behavior_info_url(self, page_url: str) -> str:
        """Creates the full URL to be used for retrial of the
        information concerning the behavior that would be used
        for the supplied page url

        :param page_url: The URL of the page to retrieve a behavior for
        :return: The full fetch behavior for a page endpoint URL
        """
        return f"{self.fetch_behavior_info_endpoint}{page_url}"

    def screenshot_endpoint_url(
        self, reqid: Optional[str] = None, format_: str = "png"
    ) -> str:
        if reqid is None:
            reqid = self.reqid
        params = f"?reqid={reqid}&target_uri={self.screenshot_target_uri}&content_type=image/{format_}"
        return f"{self.screenshot_api_url}{params}"

    def get(self, key: Any, default: Any = None) -> Any:
        value = self.config_value(key)
        if value is None:
            return default
        return value

    def config_value(self, key: Any) -> Any:
        if self.additional_configuration is not None:
            value = self.additional_configuration.get(key)
            if value is not None:
                return value
        return getattr(self, key, None)


def build_automation_config(
    options: Optional[Dict] = None, **kwargs: Any
) -> AutomationConfig:
    """

    :param options: Optional additional configuration options supplied as an dict
    :param kwargs: Optional additional configuration options supplied as keyword args
    :return: The automation config class to be used for the running automation
    """
    browser_host = env("BROWSER_HOST")
    behavior_api_url = env("BEHAVIOR_API_URL", default="http://localhost:3030")
    conf = dict(
        redis_url=env("REDIS_URL", default="redis://localhost"),
        tab_type=env("TAB_TYPE", default="BehaviorTab"),
        browser_id=env("BROWSER_ID", default="chrome:67"),
        browser_host=browser_host,
        browser_host_ip=get_browser_host_ip(browser_host),
        shepherd_host=env("SHEPHERD_HOST", default="http://shepherd:9020"),
        num_tabs=env("NUM_TABS", type_=int, default=1),
        autoid=env("AUTO_ID", default=""),
        reqid=env("REQ_ID", default=""),
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
        screenshot_api_url=env("SCREENSHOT_API_URL"),
        screenshot_target_uri=env("SCREENSHOT_TARGET_URI"),
        screenshot_format=env("SCREENSHOT_FORMAT"),
        cdp_port=env("CDP_PORT", default="9222"),
        req_browser_path=env("REQ_BROWSER_PATH", default="/request_browser/"),
        init_browser_pathq=env("REQ_BROWSER_PATH", default="/init_browser?reqid="),
        browser_info_path=env("GET_BROWSER_INFO_URL", default="/info/"),
        behavior_action_expression=env(
            "BEHAVIOR_ACTION_EXPRESSION", default="window.$WRIteratorHandler$()"
        ),
        behavior_paused_expression=env(
            "BEHAVIOR_PAUSED_EXPRESSION", default="window.$WBBehaviorPaused === true"
        ),
        page_url_expression=env("PAGE_URL_EXPRESSION", default="window.location.href"),
        outlinks_expression=env("OUTLINKS_EXPRESSION", default="window.$wbOutlinks$"),
        clear_outlinks_expression=env(
            "CLEAR_OUTLINKS_EXPRESSION", default="window.$wbOutlinkSet$.clear()"
        ),
        no_out_links_express=env(
            "NO_OUT_LINKS_EXPRESS", default="window.$WBNOOUTLINKS = true;"
        ),
    )
    user_conf = dict()
    if options is not None:
        user_conf.update(options)
    user_conf.update(kwargs)
    if len(user_conf):
        additional_configuration = dict()
        for override_key, override_value in user_conf.items():
            if override_key in conf:
                conf[override_key] = override_value
            else:
                additional_configuration[override_key] = override_value
        if len(additional_configuration):
            conf["additional_configuration"] = additional_configuration
    logger.info("autobrowser operating with configuration")
    for k, v in conf.items():
        logger.info(f"  {k} -> {v}")
    return AutomationConfig(**conf)


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

    auto_info: AutomationConfig = attr_ib()
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
