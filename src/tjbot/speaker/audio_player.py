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
