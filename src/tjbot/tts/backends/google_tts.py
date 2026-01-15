import os
import logging
from typing import Optional
from ..engine import TTSEngine
from ...config.models import GoogleCloudTTSConfig
from ...error import TJBotError

try:
    from google.cloud import texttospeech
except ImportError:
    texttospeech = None

logger = logging.getLogger(__name__)

class GoogleCloudTTSEngine(TTSEngine):
    """
    Google Cloud Text-to-Speech backend.
    """
    def __init__(self, config: Optional[GoogleCloudTTSConfig] = None):
        self.backend_config = config
        self.client = None
        self._initialize()

    def _initialize(self):
        if texttospeech is None:
             raise TJBotError("google-cloud-texttospeech library not installed. Please install it.")

        # Google Cloud auth setup
        if self.backend_config and self.backend_config.keyFilename:
             os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.backend_config.keyFilename

        try:
            self.client = texttospeech.TextToSpeechClient()
            logger.info("Google TTS initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google TTS: {e}")

    def synthesize(self, text: str) -> bytes:
        if not self.client:
             raise TJBotError("Google TTS not initialized.")

        # Mapping config
        language_code = self.backend_config.languageCode if self.backend_config else 'en-US'
        name = self.backend_config.name # Voice name
        ssml_gender_str = self.backend_config.ssmlGender # MALE, FEMALE, NEUTRAL

        ssml_gender = texttospeech.SsmlVoiceGender.NEUTRAL
        if ssml_gender_str == 'MALE':
            ssml_gender = texttospeech.SsmlVoiceGender.MALE
        elif ssml_gender_str == 'FEMALE':
            ssml_gender = texttospeech.SsmlVoiceGender.FEMALE

        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=name,
            ssml_gender=ssml_gender
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )

        synthesis_input = texttospeech.SynthesisInput(text=text)

        try:
            response = self.client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            return response.audio_content
        except Exception as e:
            logger.error(f"Google TTS synthesis error: {e}")
            raise TJBotError(f"Google TTS error: {e}")
