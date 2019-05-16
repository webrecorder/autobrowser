# fmt: off
from better_exceptions import hook as be_hook; be_hook()
# fmt: on
import logging
from typing import Any, Optional, Union

__all__ = ["AutoLogger", "RootLogger", "create_autologger"]

logging.basicConfig(
    format="<%(asctime)s %(levelname)s> %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

RootLogger = logging.getLogger("autobrowser")


class AutoLogger:
    """Logging logger wrapper that simplifies the logging format used by autobrowser"""

    __slots__ = ["__weakref__", "class_name", "logging_instance"]

    def __init__(self, class_name: str, logging_instance: logging.Logger) -> None:
        self.class_name: str = class_name
        self.logging_instance: logging.Logger = logging_instance

    def critical(
        self,
        method: str,
        msg: str,
        exc_info: Optional[Union[bool, BaseException]] = None,
    ) -> None:
        self.logging_instance.critical(
            f"{self.class_name}[{method}]: {msg}", exc_info=exc_info
        )

    def debug(self, method: str, msg: str) -> None:
        self.logging_instance.debug(f"{self.class_name}[{method}]: {msg}")

    def error(self, method: str, msg: str) -> None:
        self.logging_instance.error(f"{self.class_name}[{method}]: {msg}")

    def exception(
        self, method: str, msg: str, exc_info: Union[bool, BaseException] = True
    ):
        self.logging_instance.exception(
            f"{self.class_name}[{method}]: {msg}", exc_info=exc_info
        )

    def log(self, level: int, method: str, msg: str) -> None:
        self.logging_instance.log(level, f"{self.class_name}[{method}]: {msg}")

    def info(self, method: str, msg: str) -> None:
        self.logging_instance.info(f"{self.class_name}[{method}]: {msg}")

    def warning(self, method: str, msg: str) -> None:
        self.logging_instance.warning(f"{self.class_name}[{method}]: {msg}")

    def warn(self, method: str, msg: str) -> None:
        self.logging_instance.warn(f"{self.class_name}[{method}]: {msg}")

    def isEnabledFor(self, level: int) -> bool:
        return self.logging_instance.isEnabledFor(level)

    def setLevel(self, level: int) -> None:
        self.logging_instance.setLevel(level)

    def findCaller(self, stack_info: bool = False) -> Any:
        return self.logging_instance.findCaller(stack_info)

    def getEffectiveLevel(self) -> int:
        return self.logging_instance.getEffectiveLevel()

    def addFilter(self, filter_: logging.Filter) -> None:
        self.logging_instance.addFilter(filter_)

    def removeFilter(self, filter_: logging.Filter) -> None:
        self.logging_instance.removeFilter(filter_)

    def __str__(self) -> str:
        return f"AutoLogger(class={self.class_name})"

    def __repr__(self) -> str:
        return self.__str__()


def create_autologger(name: str, class_name: str) -> AutoLogger:
    """Creates a new AutoLogger instance for the specified class

    :param name: The name for the new child logger
    :param class_name: The name of the class the new AutoLogger is for
    :return: The new AutoLogger
    """
    return AutoLogger(class_name, RootLogger.getChild(name))
