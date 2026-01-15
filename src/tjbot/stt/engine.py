from abc import ABC, abstractmethod
from typing import Iterator, Callable, Optional
from ..config.models import STTEngineConfig

class STTEngine(ABC):
    """
    Abstract base class for STT engines.
    """
    def __init__(self, config: STTEngineConfig):
        self.config = config

    @abstractmethod
    def transcribe(
        self,
        audio_stream: Iterator[bytes],
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> str:
        """
        Transcribe audio stream.
        This method should block until transcription is complete (e.g. end of stream).
        :param audio_stream: Iterator returning bytes of audio data.
        :param on_partial_result: Callback for partial transcripts.
        :param on_final_result: Callback for final transcripts (if intermediate finals occur).
        :param on_error: Callback for errors.
        :return: Final full transcript.
        """
        pass
