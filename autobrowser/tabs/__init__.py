# -*- coding: utf-8 -*-
from typing import Any, Dict, Type, TYPE_CHECKING

from .behaviorTab import BehaviorTab
from .crawlerTab import CrawlerTab
from .basetab import BaseAutoTab

if TYPE_CHECKING:
    from autobrowser.browser import Browser  # noqa: F401

__all__ = ["BaseAutoTab", "BehaviorTab", "TAB_CLASSES", "create_tab"]

TAB_CLASSES: Dict[str, Type[BaseAutoTab]] = dict(
    BehaviorTab=BehaviorTab, CrawlerTab=CrawlerTab
)


def create_tab(browser: "Browser", tab_data: Dict, **kwargs: Any) -> BaseAutoTab:
    return TAB_CLASSES[browser.automation.tab_type].create(
        browser=browser, tab_data=tab_data, **kwargs
    )
