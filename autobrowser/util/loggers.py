import better_exceptions

better_exceptions.hook()
import logging
import attr

__all__ = ["RootLogger", "AutoLogger"]

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

RootLogger = logging.getLogger("autobrowser")


@attr.dataclass(slots=True)
class AutoLogger:
    class_name: str = attr.ib()
    logging_instance: logging.Logger = attr.ib()

    def debug(self, msg, *args, **kwargs):
        self.logging_instance.debug(f"{self.class_name}{msg}", *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logging_instance.info(f"{self.class_name}{msg}", *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logging_instance.warning(f"{self.class_name}{msg}", *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self.logging_instance.warn(f"{self.class_name}{msg}", *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logging_instance.error(f"{self.class_name}{msg}", *args, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        self.logging_instance.exception(
            f"{self.class_name}{msg}", *args, exc_info=exc_info, **kwargs
        )

    def critical(self, msg, *args, **kwargs):
        self.logging_instance.critical(f"{self.class_name}{msg}", *args, **kwargs)
