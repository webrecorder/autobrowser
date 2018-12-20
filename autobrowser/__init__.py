# -*- coding: utf-8 -*-
import logging

from .automation import build_automation_config
from .browser import Browser
from .behaviors import AutoScrollBehavior, Behavior, ScrollBehavior, BehaviorManager
from .drivers import SingleBrowserDriver, MultiBrowserDriver, LocalBrowserDiver
from .tabs import Tab, BehaviorTab, TAB_CLASSES
from .util import NetworkIdleMonitor, monitor, Helper
from .errors import AutoTabError, AutoBrowserError, BrowserInitError
from .exit_code_aware_runner import run_automation

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

__all__ = [
    "AutoBrowserError",
    "AutoTabError",
    "AutoScrollBehavior",
    "BrowserInitError",
    "Browser",
    "build_automation_config",
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
    "run_automation"
]
