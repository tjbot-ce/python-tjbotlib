from .utils.logging import init_logging

init_logging("info")

from .tjbot import TJBot

__all__ = ["TJBot"]
