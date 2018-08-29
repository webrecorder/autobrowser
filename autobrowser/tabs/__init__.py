# -*- coding: utf-8 -*-
from typing import Dict

from .basetab import AutoTabError, BaseAutoTab
from .behaviorTab import BehaviorTab

__all__ = ["AutoTabError", "BaseAutoTab", "BehaviorTab", "TAB_CLASSES"]


TAB_CLASSES: Dict[str, BaseAutoTab] = dict(BehaviorTab=BehaviorTab)
