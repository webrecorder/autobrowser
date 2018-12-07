from typing import Dict
import attr

__all__ = ["AutomationInfo"]


@attr.dataclass(slots=True)
class AutomationInfo(object):
    api_host: str = attr.ib(default="http://shepherd:9020")
    tab_class: str = attr.ib(default="BehaviorTab")
    autoid: str = attr.ib(default="")
    reqid: str = attr.ib(default="")
    ip: str = attr.ib(default=None)


@attr.dataclass(slots=True)
class TabInfo(object):
    ws_url: str = attr.ib()
    id: str = attr.ib()
    autoid: str = attr.ib(default="")
