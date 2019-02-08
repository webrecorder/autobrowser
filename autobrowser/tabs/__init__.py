from typing import Any, Dict, Type

from autobrowser.abcs import Browser, Tab
from .basetab import BaseTab
from .behaviorTab import BehaviorTab
from .crawlerTab import CrawlerTab

__all__ = ["BaseTab", "BehaviorTab", "CrawlerTab", "TAB_CLASSES", "create_tab"]

TAB_CLASSES: Dict[str, Type[Tab]] = dict(BehaviorTab=BehaviorTab, CrawlerTab=CrawlerTab)


async def create_tab(browser: Browser, tab_data: Dict, **kwargs: Any) -> Tab:
    tab = TAB_CLASSES[browser.automation_info.tab_type].create(
        browser=browser, tab_data=tab_data, **kwargs
    )
    await tab.init()
    return tab
