from typing import Any, Dict, Type

from autobrowser.abcs import Browser, Tab
from .basetab import BaseTab
from .behaviorTab import BehaviorTab
from .crawlerTab import CrawlerTab

__all__ = ["BaseTab", "BehaviorTab", "CrawlerTab", "TAB_CLASSES", "create_tab"]

TAB_CLASSES: Dict[str, Type[Tab]] = dict(BehaviorTab=BehaviorTab, CrawlerTab=CrawlerTab)


async def create_tab(browser: Browser, tab_data: Dict, **kwargs: Any) -> Tab:
    """Creates a new instance of a tab and returns it

    :param browser: An instance of a browser class the new tab class instance lives in
    :param tab_data: The data describing the actual browser tab
    :param kwargs: Additional arguments supplied to the `create` method of the tab classes
    :return:
    """
    tab = TAB_CLASSES[browser.config.tab_type].create(
        browser=browser, tab_data=tab_data, **kwargs
    )
    await tab.init()
    return tab
