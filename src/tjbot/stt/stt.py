import logging
from typing import TYPE_CHECKING, Iterator, Optional

from ..config.config_types import ListenConfig
from ..utils.errors import TJBotError
from .stt_engine import STTEngine, STTRequestOptions, create_stt_engine

if TYPE_CHECKING:
    from ..microphone import MicrophoneController

logger = logging.getLogger(__name__)


class STTController:
    """STT controller that manages transcription engine lifecycle."""

    def __init__(
        self,
        listen_config: Optional[ListenConfig] = None,
        microphone_controller: Optional["MicrophoneController"] = None,
    ):
        self.config: Optional[ListenConfig] = None
        self.engine: Optional[STTEngine] = None
        self.microphone_controller = microphone_controller

        if listen_config is not None:
            self.initialize(listen_config)

    def initialize(self, listen_config: ListenConfig) -> None:
        self.config = listen_config
        self.engine = create_stt_engine(listen_config)

        microphone_rate = listen_config.microphone_rate or 44100
        microphone_channels = listen_config.microphone_channels or 2
        self.engine.initialize(microphone_rate, microphone_channels)

    def _is_no_speech_error(self, error: Exception) -> bool:
        return isinstance(error, TJBotError) and error.code == "stt.no-speech"

    def transcribe(
        self,
        options: Optional[STTRequestOptions] = None,
    ) -> str:
        if self.config is None or self.engine is None:
            raise TJBotError("STT engine not initialized. Call initialize() before transcribing.")

        if self.microphone_controller is None:
            raise TJBotError("Microphone controller is not available for STT transcription.")

        options = options or {}

        self.engine.raise_if_aborted(options)

        while True:
            self.microphone_controller.start()
            active_stream: Iterator[bytes] = self.microphone_controller.get_input_stream()

            try:
                transcript = self.engine.transcribe(active_stream, options)
                logger.debug("Transcript: %s", transcript)
                return transcript
            except Exception as error:
                if self._is_no_speech_error(error):
                    self.engine.raise_if_aborted(options)
                    logger.debug("No speech detected; continuing to listen")
                    continue
                raise
            finally:
                self.microphone_controller.pause()

    def cleanup(self) -> None:
        if self.engine is not None:
            self.engine.cleanup()
            self.engine = None
