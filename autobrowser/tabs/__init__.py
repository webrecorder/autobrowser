# -*- coding: utf-8 -*-
from typing import Any, Dict, Type, TYPE_CHECKING

from .behaviorTab import BehaviorTab
from .crawlerTab import CrawlerTab
from .basetab import Tab

if TYPE_CHECKING:
    from autobrowser.browser import Browser  # noqa: F401

__all__ = ["Tab", "BehaviorTab", "TAB_CLASSES", "create_tab"]

TAB_CLASSES: Dict[str, Type[Tab]] = dict(
    BehaviorTab=BehaviorTab, CrawlerTab=CrawlerTab
)


async def create_tab(browser: "Browser", tab_data: Dict, **kwargs: Any) -> Tab:
    tab = TAB_CLASSES[browser.conf.tab_type].create(
        browser=browser, tab_data=tab_data, **kwargs
    )
    await tab.init()
    return tab
