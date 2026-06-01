import asyncio
import time
import shutil


async def sleep(sec: float) -> None:
    """
    Put TJBot to sleep asynchronously.
    :param sec: Number of seconds to sleep for.
    """
    await asyncio.sleep(sec)


def sleep_sync(sec: float) -> None:
    """
    Put TJBot to sleep synchronously (blocking).
    :param sec: Number of seconds to sleep for.
    """
    time.sleep(sec)


def is_command_available(command: str) -> bool:
    """
    Check if a command-line tool is available in PATH.
    :param command: The command to check for.
    :return: True if command is available, False otherwise.
    """
    return shutil.which(command) is not None
