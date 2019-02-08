import logging

from .abcs import Behavior, BehaviorManager, Browser, Driver, Tab
from .automation import (
    AutomationConfig,
    AutomationInfo,
    BrowserExitInfo,
    CloseReason,
    RedisKeys,
    ShutdownCondition,
    TabClosedInfo,
    build_automation_config,
    exit_code_from_reason,
)
from .behaviors import LocalBehaviorManager, RemoteBehaviorManager, WRBehaviorRunner
from .chrome_browser import Chrome
from .drivers import (
    BaseDriver,
    LocalBrowserDiver,
    MultiBrowserDriver,
    SingleBrowserDriver,
)
from .errors import (
    AutoBrowserError,
    AutoTabError,
    BrowserInitError,
    BrowserStagingError,
    DriverError,
)
from .exit_code_aware_runner import run_automation
from .tabs import BaseTab, BehaviorTab, CrawlerTab, TAB_CLASSES
from .util import NetworkIdleMonitor, monitor, Helper

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

__all__ = [
    "AutoBrowserError",
    "AutoTabError",
    "AutomationConfig",
    "AutomationInfo",
    "BaseDriver",
    "BaseTab",
    "Behavior",
    "BehaviorManager",
    "BehaviorTab",
    "Browser",
    "BrowserExitInfo",
    "BrowserInitError",
    "BrowserStagingError",
    "Chrome",
    "CloseReason",
    "CrawlerTab",
    "Driver",
    "DriverError",
    "Helper",
    "LocalBrowserDiver",
    "LocalBehaviorManager",
    "MultiBrowserDriver",
    "NetworkIdleMonitor",
    "RedisKeys",
    "RemoteBehaviorManager",
    "ShutdownCondition",
    "SingleBrowserDriver",
    "TAB_CLASSES",
    "Tab",
    "TabClosedInfo",
    "WRBehaviorRunner",
    "build_automation_config",
    "exit_code_from_reason",
    "monitor",
    "run_automation",
]
