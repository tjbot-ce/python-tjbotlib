import subprocess
import os
from typing import Optional, Callable
from ..utils import is_command_available
from ..error import TJBotError

class SpeakerController:
    """
    TJBot Speaker Controller.
    Uses 'aplay' for audio playback.
    """
    def __init__(self):
        self.device = ''
        self.on_pause_listening: Optional[Callable[[], None]] = None
        self.on_resume_listening: Optional[Callable[[], None]] = None

    def initialize(self, device: str = '') -> None:
        self.device = device
        if not is_command_available('aplay'):
            print("Warning: 'aplay' command not found. Audio playback may fail.")

    def set_audio_lifecycle_callbacks(self, on_pause: Callable[[], None], on_resume: Callable[[], None]) -> None:
        self.on_pause_listening = on_pause
        self.on_resume_listening = on_resume

    def play_audio(self, file_path: str) -> None:
        """
        Play an audio file.
        :param file_path: Path to the audio file (WAV).
        """
        if not os.path.exists(file_path):
             raise TJBotError(f"Audio file not found: {file_path}")

        # Pause listening to avoid hearing itself
        if self.on_pause_listening:
            self.on_pause_listening()

        cmd = ['aplay', file_path]
        if self.device:
            cmd.extend(['-D', self.device])

        try:
            # Blocking playback? Node implementation waits.
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise TJBotError(f"Error playing audio: {e}")
        finally:
            if self.on_resume_listening:
                self.on_resume_listening()
