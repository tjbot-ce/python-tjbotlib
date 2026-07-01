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

import errno
import re
import select
import signal
import subprocess
import threading
from typing import Iterator, Optional

from ..utils.errors import TJBotError
from ..utils import is_command_available
from ..utils.logging import get_logger

_logger = get_logger(__name__)


class _MicrophoneInputStream:
    """Iterator/file-like adapter over the controller's live arecord stdout.

    Uses select() with a short timeout instead of a blocking read so that
    stop() can interrupt the iterator from another thread within ~50 ms.
    """

    def __init__(self, controller: "MicrophoneController"):
        self._controller = controller
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Signal this stream to stop yielding chunks."""
        self._stop_event.set()

    def __iter__(self) -> Iterator[bytes]:
        bytes_per_sample = 2
        chunk_bytes = (
            self._controller._chunk_size * self._controller._channels * bytes_per_sample
        )

        while (
            not self._stop_event.is_set()
            and self._controller._is_started
            and self._controller._mic_process
        ):
            process = self._controller._mic_process
            if not process.stdout:
                break

            try:
                ready, _, _ = select.select([process.stdout], [], [], 0.05)
            except (ValueError, OSError):
                break

            if not ready:
                continue

            try:
                chunk = process.stdout.read(chunk_bytes)
            except OSError as error:
                if error.errno == errno.EBADF:
                    _logger.debug("microphone stream closed during shutdown")
                    break
                raise
            if not chunk:
                break

            # TODO: we need to introduce a 'silly' level for stuff like this
            # _logger.debug("microphone received %d bytes", len(chunk))
            yield chunk

    def read(self, size: int) -> bytes:
        process = self._controller._mic_process
        if not process or not process.stdout or not self._controller._is_started:
            return b""

        try:
            chunk = process.stdout.read(size)
        except OSError as error:
            if error.errno == errno.EBADF:
                _logger.debug("microphone stream closed during shutdown")
                return b""
            raise
        return chunk or b""


class MicrophoneController:
    """Microphone controller for TJBot."""

    def __init__(self):
        self._mic_process: Optional[subprocess.Popen[bytes]] = None
        self._is_started = False
        self._is_paused = False

        self._rate = 16000
        self._channels = 1
        self._device = ""
        self._chunk_size = 1024

    def _detect_microphone_device(self) -> str:
        """Auto-detect the first available audio recording device."""
        if not is_command_available("arecord"):
            _logger.warning("arecord command not found")
            return ""

        try:
            output = subprocess.check_output(
                ["arecord", "-l"], text=True, stderr=subprocess.DEVNULL
            )
        except Exception as error:
            _logger.error("error detecting microphone device: %s", error)
            return ""

        match = re.search(r"card\s+(\d+):.*device\s+(\d+):", output)
        if not match:
            _logger.warning("no audio capture devices found")
            return ""

        card = match.group(1)
        device = match.group(2)
        device_string = f"plughw:{card},{device}"
        _logger.debug("auto-detected microphone device: %s", device_string)
        return device_string

    def initialize(
        self,
        rate: int,
        channels: int,
        device: Optional[str] = None,
    ) -> None:
        """Initialize microphone configuration (does not start recording)."""
        self._rate = rate
        self._channels = channels

        if device and device != "":
            self._device = device
            _logger.debug(
                "initializing microphone with user-defined audio device: %s",
                device,
            )
        else:
            selected_device = self._detect_microphone_device()
            self._device = selected_device
            _logger.debug(
                "initializing microphone with auto-detected audio device: %s",
                selected_device,
            )

        _logger.debug(
            "initialized microphone with config: rate=%s channels=%s device=%s",
            rate,
            channels,
            self._device,
        )

    def start(self) -> None:
        """Start microphone recording."""
        if self._mic_process is not None and self._is_started and not self._is_paused:
            return

        if self._mic_process is not None and self._is_started and self._is_paused:
            self.resume()
            return

        if not is_command_available("arecord"):
            raise TJBotError("arecord command not found. Install alsa-utils.")

        cmd = [
            "arecord",
            "-q",
            "-t",
            "raw",
            "-f",
            "S16_LE",
            "-r",
            str(self._rate),
            "-c",
            str(self._channels),
        ]

        if self._device:
            cmd.extend(["-D", self._device])

        self._mic_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self._is_started = True
        self._is_paused = False
        _logger.debug("microphone started")

    def pause(self) -> None:
        """Pause microphone recording."""
        if (
            self._mic_process
            and self._mic_process.poll() is None
            and self._is_started
            and not self._is_paused
        ):
            self._mic_process.send_signal(signal.SIGSTOP)
            self._is_paused = True
            _logger.debug("microphone paused")

    def resume(self) -> None:
        """Resume microphone recording."""
        if (
            self._mic_process
            and self._mic_process.poll() is None
            and self._is_started
            and self._is_paused
        ):
            self._mic_process.send_signal(signal.SIGCONT)
            self._is_paused = False
            _logger.debug("microphone resumed")

    def stop(self) -> None:
        """Stop microphone recording."""
        if not self._mic_process:
            return

        process = self._mic_process
        self._is_started = False
        self._is_paused = False

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()

        if process.stdout:
            process.stdout.close()

        self._mic_process = None
        _logger.debug("microphone stopped")

    def get_input_stream(self) -> _MicrophoneInputStream:
        """Get the microphone input stream.

        Returns a fresh _MicrophoneInputStream instance to avoid iterator state
        issues when multiple transcriptions occur in sequence. Each call creates
        a new iterator adapter over the same subprocess stdout.
        """
        if not self._is_started:
            self.start()
        return _MicrophoneInputStream(self)

    def cleanup(self) -> None:
        """Clean up resources."""
        _logger.debug("MicrophoneController cleanup")
        self.stop()
