try:
    import alsaaudio
except ImportError:
    alsaaudio = None

import queue
import threading
from typing import Optional, Iterator
from ..error import TJBotError

class MicrophoneStream:
    """
    Microphone stream that acts as an iterator or file-like object.
    It captures audio from ALSA and yields chunks.
    """
    def __init__(self, rate: int, channels: int, chunk_size: int, device: str = 'default'):
        self.rate = rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.device = device
        self._buff = queue.Queue()
        self.closed = True
        self.pcm: Optional['alsaaudio.PCM'] = None
        self._thread: Optional[threading.Thread] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    def start(self):
        if not self.closed:
            return

        if not alsaaudio:
            raise TJBotError("pyalsaaudio is not installed")

        self.closed = False

        # Open ALSA PCM device for recording
        self.pcm = alsaaudio.PCM(
            type=alsaaudio.PCM_CAPTURE,
            mode=alsaaudio.PCM_NORMAL,
            device=self.device
        )

        # Set attributes
        self.pcm.setchannels(self.channels)
        self.pcm.setrate(self.rate)
        self.pcm.setformat(alsaaudio.PCM_FORMAT_S16_LE)  # 16-bit signed little-endian
        self.pcm.setperiodsize(self.chunk_size)

        # Start capture thread
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.closed = True
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self.pcm:
            self.pcm.close()
            self.pcm = None
        # Signal end of stream
        self._buff.put(None)

    def _capture_loop(self):
        """Background thread that continuously reads from ALSA"""
        while not self.closed and self.pcm:
            try:
                # Read audio data
                length, data = self.pcm.read()
                if length > 0:
                    self._buff.put(data)
            except Exception as e:
                if not self.closed:
                    print(f"Error reading from microphone: {e}")
                break

    def generator(self) -> Iterator[bytes]:
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            yield chunk

    def read(self, size: int) -> bytes:
        # File-like interface (blocking) - simplistic implementation
        # Note: 'size' is usually ignored in streaming contexts or treated as max bytes
        chunk = self._buff.get()
        if chunk is None:
            return b""
        return chunk


class MicrophoneController:
    """
    TJBot Microphone Controller.
    """
    def __init__(self):
        self.rate = 16000
        self.channels = 1
        self.device = 'default'
        self.stream: Optional[MicrophoneStream] = None

    def initialize(self, rate: int = 16000, channels: int = 1, device_name: str = "") -> None:
        self.rate = rate
        self.channels = channels

        if device_name:
            # Use the device name directly for ALSA
            self.device = device_name
        else:
            self.device = 'default'

    def start(self) -> None:
        if self.stream and not self.stream.closed:
            return # Already started

        self.stream = MicrophoneStream(
            rate=self.rate,
            channels=self.channels,
            chunk_size=1024,
            device=self.device
        )
        self.stream.start()

    def stop(self) -> None:
        if self.stream:
            self.stream.stop()
            self.stream = None

    def pause(self) -> None:
        # ALSA doesn't have native pause/resume, so we stop/start
        # For now, we'll just leave it running or implement stop/start
        pass

    def resume(self) -> None:
        # ALSA doesn't have native pause/resume
        pass

    def get_input_stream(self) -> Iterator[bytes]:
        """
        Returns a generator yielding audio chunks.
        """
        if not self.stream:
            raise TJBotError("Microphone not started")
        return self.stream.generator()
