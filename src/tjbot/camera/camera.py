import os
import subprocess
import tempfile
from typing import Tuple, Optional
from ..utils import is_command_available
from ..error import TJBotError

class CameraController:
    """
    TJBot Camera Controller.
    Supports 'libcamera-still' (modern RPi OS) and 'raspistill' (legacy).
    """

    def __init__(self):
        self.width = 1920
        self.height = 1080
        self.vertical_flip = False
        self.horizontal_flip = False
        self.camera_cmd = None

        if is_command_available('libcamera-still'):
            self.camera_cmd = 'libcamera-still'
        elif is_command_available('raspistill'):
            self.camera_cmd = 'raspistill'
        else:
            print("Warning: No camera command found (libcamera-still or raspistill). Camera will not work.")

    def initialize(self, resolution: Tuple[int, int], vertical_flip: bool, horizontal_flip: bool) -> None:
        """
        Initialize camera settings.
        :param resolution: (width, height) tuple.
        :param vertical_flip: Whether to flip vertically.
        :param horizontal_flip: Whether to flip horizontally.
        """
        self.width = resolution[0]
        self.height = resolution[1]
        self.vertical_flip = vertical_flip
        self.horizontal_flip = horizontal_flip

    def capture_photo(self, file_path: Optional[str] = None) -> str:
        """
        Capture a photo.
        :param file_path: Path to save the photo. If None, saves to a temporary file.
        :return: Path to the saved photo.
        """
        if not self.camera_cmd:
            raise TJBotError("Camera hardware not found or not supported.")

        if not file_path:
            # Create a temp file
            fd, file_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)

        cmd = [self.camera_cmd, "-o", file_path]

        # Add resolution
        if self.camera_cmd == 'libcamera-still':
            cmd.extend(["--width", str(self.width), "--height", str(self.height)])
            cmd.extend(["-n", "-t", "1"]) # No preview, timeout 1ms (immediate)
            if self.vertical_flip:
                cmd.append("--vflip")
            if self.horizontal_flip:
                cmd.append("--hflip")
        elif self.camera_cmd == 'raspistill':
            cmd.extend(["-w", str(self.width), "-h", str(self.height)])
            cmd.extend(["-n", "-t", "1"])
            if self.vertical_flip:
                cmd.append("-vf")
            if self.horizontal_flip:
                cmd.append("-hf")

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            raise TJBotError(f"Error capturing photo with {self.camera_cmd}: {e}")

        return file_path
