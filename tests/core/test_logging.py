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

import logging

from tjbot.utils.logging import TJBotLogFormatter, init_logging, set_log_level


def test_init_logging_maps_debug_level() -> None:
    init_logging("debug")
    logger = logging.getLogger("tjbot")

    assert logger.level == logging.DEBUG


def test_set_log_level_maps_warn_level() -> None:
    set_log_level("warn")
    logger = logging.getLogger("tjbot")

    assert logger.level == logging.WARNING


def test_formatter_adds_module_emoji_prefix() -> None:
    formatter = TJBotLogFormatter()
    record = logging.LogRecord(
        name="tjbot.stt.backends.google_cloud_stt",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="backend initialized",
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert rendered.startswith("info: 🦻 ")
    assert "backend initialized" in rendered
