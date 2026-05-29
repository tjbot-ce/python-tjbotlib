import os
import tempfile
import logging
from typing import Optional
from ..config.config_types import SpeakConfig
from ..utils.errors import TJBotError
from .tts_engine import TTSEngine, create_tts_engine
from ..speaker import SpeakerController

logger = logging.getLogger(__name__)


class TTSController:
    """
    TTS Controller that manages the active TTS engine and speaks via SpeakerController.
    """

    def __init__(self, speaker_controller: SpeakerController):
        self.speaker = speaker_controller
        self.engine: Optional[TTSEngine] = None

    def initialize(self, speak_config: SpeakConfig) -> None:
        engine = create_tts_engine(speak_config)
        if engine is None:
            self.engine = None
            return
        engine.initialize()
        self.engine = engine

    def cleanup(self) -> None:
        if self.engine is not None:
            self.engine.cleanup()
            self.engine = None

    def speak(self, text: str) -> None:
        if not self.engine:
            raise TJBotError(
                "TTS engine not initialized. Call initialize() before speaking."
            )

        if not text or not text.strip():
            raise TJBotError("Text to speak cannot be empty")

        try:
            logger.debug("Synthesizing speech...")
            audio_data = self.engine.synthesize(text)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file_obj:
                file_obj.write(audio_data)
                temp_path = file_obj.name

            try:
                self.speaker.play_audio(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception:
            logger.exception("Error during speech synthesis")
            raise
