# -*- coding: utf-8 -*-
import logging

from .browser import Browser, DynamicBrowser
from .behaviors import AutoScrollBehavior, Behavior, ScrollBehavior, BehaviorManager
from .driver import Driver, run_driver, SingleBrowserDriver
from .tabs import BaseAutoTab, BehaviorTab, TAB_CLASSES
from .util import NetworkIdleMonitor, monitor, Helper
from .errors import AutoTabError, AutoBrowserError, BrowserInitError

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

__all__ = [
    "AutoBrowserError",
    "AutoTabError",
    "AutoScrollBehavior",
    "BrowserInitError",
    "Browser",
    "BaseAutoTab",
    "Behavior",
    "BehaviorTab",
    "BehaviorManager",
    "DynamicBrowser",
    "Driver",
    "Helper",
    "monitor",
    "NetworkIdleMonitor",
    "run_driver",
    "SingleBrowserDriver",
    "ScrollBehavior",
    "TAB_CLASSES",
]
