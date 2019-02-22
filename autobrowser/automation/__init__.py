from .details import (
    AutomationConfig,
    AutomationInfo,
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
    "AutomationInfo",
    "BrowserExitInfo",
    "CloseReason",
    "RedisKeys",
    "ShutdownCondition",
    "TabClosedInfo",
    "build_automation_config",
    "exit_code_from_reason",
]
