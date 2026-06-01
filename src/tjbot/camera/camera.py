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

import os
import subprocess
import tempfile
from typing import Tuple, Optional
import logging
from ..utils.errors import TJBotError


logger = logging.getLogger(__name__)


class CameraController:
    """
    TJBot Camera Controller.
    Handles camera initialization and photo capture using rpicam-still.
    """

    def __init__(self):
        self.resolution: Tuple[int, int] = (1920, 1080)
        self.vertical_flip = False
        self.horizontal_flip = False
        self.capture_timeout = 500
        self.zero_shutter_lag = False

    def initialize(
        self,
        resolution: Tuple[int, int],
        vertical_flip: bool,
        horizontal_flip: bool,
        capture_timeout: int = 500,
        zero_shutter_lag: bool = False,
    ) -> None:
        """
        Initialize camera settings.
        :param resolution: (width, height) tuple.
        :param vertical_flip: Whether to flip vertically.
        :param horizontal_flip: Whether to flip horizontally.
        """
        self.resolution = resolution
        self.vertical_flip = vertical_flip
        self.horizontal_flip = horizontal_flip
        self.capture_timeout = capture_timeout
        self.zero_shutter_lag = zero_shutter_lag

        logger.debug(
            "Initialized camera with config: resolution=%sx%s, vertical_flip=%s, horizontal_flip=%s, capture_timeout=%sms, zero_shutter_lag=%s",
            resolution[0],
            resolution[1],
            vertical_flip,
            horizontal_flip,
            capture_timeout,
            zero_shutter_lag,
        )

    def build_camera_args(
        self, output_path: str, encoding: Optional[str] = None
    ) -> list[str]:
        """
        Build rpicam-still command arguments.
        :param output_path: Output path or '-' for stdout.
        :param encoding: Optional encoding format (for example 'jpg').
        :return: List of command-line arguments.
        """
        args = [
            "--output",
            output_path,
            "--width",
            str(self.resolution[0]),
            "--height",
            str(self.resolution[1]),
            "--nopreview",
            "--camera",
            "0",
        ]

        if encoding:
            args.extend(["--encoding", encoding])

        if self.vertical_flip:
            args.append("--vflip")
        if self.horizontal_flip:
            args.append("--hflip")

        if self.capture_timeout == 0:
            args.append("--immediate")
        else:
            args.extend(["--timeout", str(self.capture_timeout)])

        if self.zero_shutter_lag:
            args.append("--zsl")

        logger.debug("Built camera args: %s", " ".join(args))
        return args

    def capture_photo(self, at_path: Optional[str] = None) -> str:
        """
        Capture a photo by invoking rpicam-still.
        :param at_path: Optional path to save the photo. If None, a temporary file will be used.
        :return: Path to the saved photo.
        """
        if not at_path:
            fd, at_path = tempfile.mkstemp(prefix="tjbot", suffix=".jpg")
            os.close(fd)

        logger.info("Capturing image at path: %s", at_path)
        cmd = ["rpicam-still", *self.build_camera_args(at_path)]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.debug(
                "rpicam-still stdout: %s", result.stdout.decode(errors="replace")
            )
            return at_path
        except (subprocess.CalledProcessError, FileNotFoundError) as err:
            stderr = ""
            if isinstance(err, subprocess.CalledProcessError):
                stderr = (err.stderr or b"").decode(errors="replace")
            message = stderr or str(err)
            logger.error("rpicam-still error: %s", message)
            raise TJBotError(message) from err

    def capture_photo_buffer(self) -> bytes:
        """
        Capture a photo and return it as bytes.
        :return: Photo bytes.
        """
        logger.info("Capturing image to buffer")
        cmd = ["rpicam-still", *self.build_camera_args("-", "jpg")]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.debug("Captured image buffer (%s bytes)", len(result.stdout))
            return result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as err:
            stderr = ""
            if isinstance(err, subprocess.CalledProcessError):
                stderr = (err.stderr or b"").decode(errors="replace")
            message = stderr or str(err)
            logger.error("rpicam-still error: %s", message)
            raise TJBotError(message) from err

    def cleanup(self) -> None:
        """Clean up resources (no-op for direct process invocation)."""
        logger.debug("CameraController cleanup (no-op for rpicam-still)")
