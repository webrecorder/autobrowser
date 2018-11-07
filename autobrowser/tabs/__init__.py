# -*- coding: utf-8 -*-
from typing import Dict, Type

from .behaviorTab import BehaviorTab
from .crawlerTab import CrawlerTab
from .basetab import BaseAutoTab
from .tabErrors import AutoTabError

__all__ = ["AutoTabError", "BaseAutoTab", "BehaviorTab", "TAB_CLASSES"]


TAB_CLASSES: Dict[str, Type[BaseAutoTab]] = dict(
    BehaviorTab=BehaviorTab, CrawlerTab=CrawlerTab
)
