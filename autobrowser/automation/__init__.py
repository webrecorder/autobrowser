from .details import (
    AutomationInfo,
    AutomationConfig,
    RedisKeys,
    TabClosedInfo,
    CloseReason,
    BrowserExitInfo,
    exit_code_from_reason,
    build_automation_config,
)
from .shutdown import ShutdownCondition

__all__ = [
    "AutomationConfig",
    "AutomationInfo",
    "BrowserExitInfo",
    "ShutdownCondition",
    "RedisKeys",
    "TabClosedInfo",
    "CloseReason",
    "exit_code_from_reason",
    "build_automation_config",
]
