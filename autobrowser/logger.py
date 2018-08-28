# -*- coding: utf-8 -*-
import logging

__all__ = ["logger"]

logging.basicConfig(
    format="%(asctime)s: [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("autobrowser")

