import os
import tempfile
import logging
from typing import Optional
from ..config.models import SpeakConfig, TTSBackendConfig
from ..error import TJBotError
from .engine import TTSEngine
from ..speaker import SpeakerController

logger = logging.getLogger(__name__)

# Import backends
# from .backends.local import LocalTTS
# ...

class TTSController:
    """
    TTS Controller that manages the active TTS engine and speaks via SpeakerController.
    """
    def __init__(self, speaker_controller: SpeakerController):
        self.speaker = speaker_controller
        self.engine: Optional[TTSEngine] = None

    def initialize_engine(self, speak_config: SpeakConfig):
        backend_config: TTSBackendConfig = speak_config.backend or TTSBackendConfig()
        backend_type = backend_config.type

        if backend_type == 'ibm-watson-tts':
            from .backends.watson import WatsonTTS
            config = backend_config.ibm_watson_tts
            self.engine = WatsonTTS(config)

        elif backend_type == 'google-cloud-tts':
            from .backends.google import GoogleTTS
            config = backend_config.google_cloud_tts
            self.engine = GoogleTTS(config)

        elif backend_type == 'azure-tts':
            from .backends.azure import AzureTTS
            config = backend_config.azure_tts
            self.engine = AzureTTS(config)

        elif backend_type == 'local':
            from .backends.sherpa import SherpaTTS
            # Same logic as STT for local config structure
            if backend_config.local and backend_config.local.sherpa_onnx:
                 self.engine = SherpaTTS(backend_config.local.sherpa_onnx)

        else:
             logger.warning(f"Unknown TTS backend type: {backend_type}")

    def speak(self, message: str, speak_config: SpeakConfig) -> None:
        if not self.engine:
            # Try to init helper if not done
             self.initialize_engine(speak_config)

        if not self.engine:
             raise TJBotError("TTS engine not initialized.")

        # Synthesize logic
        audio_data = self.engine.synthesize(message)

        # Save to temp file and play
        # TODO: If SpeakerController supports stream, use that.
        # But for now assuming file based.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            self.speaker.play_audio(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
