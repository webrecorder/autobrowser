# -*- coding: utf-8 -*-
import logging

from .basebrowser import BaseAutoBrowser
from .behaviors import AutoScrollBehavior, Behavior, ScrollBehavior
from .driver import Driver
from .tabs import AutoTabError, BaseAutoTab, BehaviorTab, TAB_CLASSES
from .util import NetworkIdleMonitor, monitor, Helper

logging.basicConfig(
    format="%(asctime)s: [%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("autobrowser")

__all__ = [
    "AutoScrollBehavior",
    "AutoTabError",
    "BaseAutoBrowser",
    "BaseAutoTab",
    "Behavior",
    "BehaviorTab",
    "ScrollBehavior",
    "Driver",
    "Helper",
    "monitor",
    "NetworkIdleMonitor",
    "TAB_CLASSES",
]
