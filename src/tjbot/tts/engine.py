from abc import ABC, abstractmethod
from ..config.models import TTSEngineConfig

class TTSEngine(ABC):
    """
    Abstract base class for TTS engines.
    """
    def __init__(self, config: TTSEngineConfig):
        self.config = config

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """
        Synthesize text to audio (WAV/PCM bytes).
        :param text: Text to speak.
        :return: WAV data as bytes.
        """
        pass
