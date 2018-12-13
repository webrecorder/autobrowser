# -*- coding: utf-8 -*-
import logging

from .browser import Browser
from .behaviors import AutoScrollBehavior, Behavior, ScrollBehavior, BehaviorManager
from .drivers import SingleBrowserDriver, MultiBrowserDriver, LocalBrowserDiver
from .tabs import Tab, BehaviorTab, TAB_CLASSES
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
    "Tab",
    "Behavior",
    "BehaviorTab",
    "BehaviorManager",
    "Helper",
    "LocalBrowserDiver",
    "monitor",
    "MultiBrowserDriver",
    "NetworkIdleMonitor",
    "SingleBrowserDriver",
    "ScrollBehavior",
    "TAB_CLASSES",
]
