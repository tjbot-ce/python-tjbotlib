# Copyright 2026-present TJBot Contributors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
