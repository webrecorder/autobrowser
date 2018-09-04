# -*- coding: utf-8 -*-
from typing import Dict

from .behaviorTab import BehaviorTab
from .basetab import AutoTabError, BaseAutoTab

__all__ = ["AutoTabError", "BaseAutoTab", "BehaviorTab", "TAB_CLASSES"]


TAB_CLASSES: Dict[str, BaseAutoTab] = dict(BehaviorTab=BehaviorTab)
