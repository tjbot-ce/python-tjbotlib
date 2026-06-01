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

import subprocess
from typing import Optional

from ..utils.errors import TJBotError
from ..utils.logging import LogEmoji, get_logger

logger = get_logger(__name__)
EMO = LogEmoji.SPEAKER


class AudioPlayer:
    """Native audio player that uses aplay for audio playback on ALSA systems."""

    def play(self, audio_path: str, device: Optional[str] = None) -> None:
        args = [audio_path]
        if device:
            args = ["-D", device, audio_path]

        logger.debug("%s Playing audio with command: aplay %s", EMO, " ".join(args))

        result = subprocess.run(
            ["aplay", *args],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            stderr_output = (result.stderr or "").strip()
            raise TJBotError(
                f"aplay exited with code {result.returncode}: {stderr_output}"
            )
