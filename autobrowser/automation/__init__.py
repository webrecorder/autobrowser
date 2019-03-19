from .details import (
    AutomationConfig,
    BrowserExitInfo,
    CloseReason,
    RedisKeys,
    TabClosedInfo,
    build_automation_config,
    exit_code_from_reason,
)
from .shutdown import ShutdownCondition

__all__ = [
    "AutomationConfig",
    "BrowserExitInfo",
    "CloseReason",
    "RedisKeys",
    "ShutdownCondition",
    "TabClosedInfo",
    "build_automation_config",
    "exit_code_from_reason",
]
