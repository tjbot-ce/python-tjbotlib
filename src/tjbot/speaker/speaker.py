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

import re
import subprocess
from typing import Optional, Callable

from ..utils.logging import get_logger
from .audio_player import AudioPlayer

logger = get_logger(__name__)


class SpeakerController:
    """
    TJBot Speaker Controller.
    Uses 'aplay' for audio playback.
    """

    def __init__(self):
        self.device = ""
        self.on_pause_callback: Optional[Callable[[], None]] = None
        self.on_resume_callback: Optional[Callable[[], None]] = None

    def _detect_speaker_device(self) -> str:
        """Auto-detect the first available audio playback device, preferring USB over HDMI."""
        try:
            output = subprocess.check_output(["aplay", "-l"], text=True)
        except Exception as error:
            logger.error("Error detecting speaker device: %s", error)
            return ""

        lines = output.splitlines()
        # Prefer USB audio devices over HDMI
        usb_line = next(
            (
                line
                for line in lines
                if "USB" in line and re.search(r"card\s+(\d+):.*device\s+(\d+):", line)
            ),
            None,
        )
        target_line = usb_line or next(
            (
                line
                for line in lines
                if re.search(r"card\s+(\d+):.*device\s+(\d+):", line)
            ),
            None,
        )

        if target_line:
            match = re.search(r"card\s+(\d+):.*device\s+(\d+):", target_line)
            if match:
                device_string = f"plughw:{match.group(1)},{match.group(2)}"
                logger.debug("auto-detected speaker device: %s", device_string)
                return device_string

        logger.warning("No audio playback devices found")
        return ""

    def initialize(self, device: str = "") -> None:
        selected_device = device or ""
        if not selected_device:
            selected_device = self._detect_speaker_device()

        self.device = selected_device
        logger.debug("Initialized speaker on device %s", self.device)

    def set_audio_lifecycle_callbacks(
        self,
        on_pause: Optional[Callable[[], None]] = None,
        on_resume: Optional[Callable[[], None]] = None,
    ) -> None:
        self.on_pause_callback = on_pause
        self.on_resume_callback = on_resume

    def play_audio(self, file_path: str) -> None:
        """
        Play an audio file.
        :param file_path: Path to the audio file (WAV).
        """
        # Pause listening to avoid hearing itself
        if self.on_pause_callback:
            self.on_pause_callback()

        player = AudioPlayer()

        if self.device:
            logger.debug(
                "Playing audio file %s through user-defined audio device (%s)",
                file_path,
                self.device,
            )
        else:
            logger.debug(
                "Playing audio file %s through default audio device", file_path
            )

        try:
            player.play(file_path, self.device)
            logger.debug("Audio playback finished")

            # Resume listening only after successful playback completion.
            if self.on_resume_callback:
                self.on_resume_callback()
        except Exception as err:
            logger.error("Error occurred while playing audio: %s", err)

    def cleanup(self) -> None:
        """Release any resources held by this controller (no-op)."""
        logger.debug("SpeakerController cleanup (no-op)")
