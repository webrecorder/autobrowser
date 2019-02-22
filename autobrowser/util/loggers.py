# fmt: off
from better_exceptions import hook as be_hook; be_hook()
# fmt: on
from typing import Any, Optional, Union
from logging import (
    Logger,
    Filter,
    basicConfig as logging_basicConfig,
    getLogger as logging_getLogger,
)
from attr import dataclass as attr_dataclass, ib as attr_ib

__all__ = ["AutoLogger", "RootLogger", "create_autologger"]

logging_basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

RootLogger = logging_getLogger("autobrowser")


@attr_dataclass(slots=True)
class AutoLogger:
    """Logging logger wrapper that simplifies the logging format used by autobrowser"""

    class_name: str = attr_ib()
    logging_instance: Logger = attr_ib(repr=False)

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

    def addFilter(self, filter_: Filter) -> None:
        self.logging_instance.addFilter(filter_)

    def removeFilter(self, filter_: Filter) -> None:
        self.logging_instance.removeFilter(filter_)


def create_autologger(name: str, class_name: str) -> AutoLogger:
    """Creates a new AutoLogger instance for the specified class

    :param name: The name for the new child logger
    :param class_name: The name of the class the new AutoLogger is for
    :return: The new AutoLogger
    """
    return AutoLogger(class_name, RootLogger.getChild(name))
