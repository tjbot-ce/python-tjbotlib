import os
import logging
from typing import Optional
from ..engine import TTSEngine
from ...config.models import IBMWatsonTTSConfig
from ...error import TJBotError

try:
    from ibm_watson import TextToSpeechV1
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
except ImportError:
    TextToSpeechV1 = None
    IAMAuthenticator = None

logger = logging.getLogger(__name__)

class IBMWatsonTTSEngine(TTSEngine):
    """
    IBM Watson Text-to-Speech backend.
    """
    def __init__(self, config: Optional[IBMWatsonTTSConfig] = None):
        self.backend_config = config
        self.service = None
        self._initialize()

    def _initialize(self):
        if TextToSpeechV1 is None:
             raise TJBotError("ibm-watson library not installed. Please install it.")

        creds_path = self._find_credentials()
        if creds_path:
             os.environ['IBM_CREDENTIALS_FILE'] = creds_path

        try:
             # Use authenticator if config has apikey
            if self.backend_config and self.backend_config.apikey:
                 authenticator = IAMAuthenticator(self.backend_config.apikey)
                 self.service = TextToSpeechV1(authenticator=authenticator)
                 if self.backend_config.url:
                     self.service.set_service_url(self.backend_config.url)
            else:
                 # Auto-load from env/file
                 self.service = TextToSpeechV1(authenticator=None)

            logger.info("Watson TTS initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Watson TTS: {e}")

    def _find_credentials(self) -> Optional[str]:
        if self.backend_config and self.backend_config.credentialsPath:
             return self.backend_config.credentialsPath

        cwd_path = os.path.join(os.getcwd(), 'ibm-credentials.env')
        if os.path.exists(cwd_path):
            return cwd_path

        home_path = os.path.expanduser('~/.tjbot/ibm-credentials.env')
        if os.path.exists(home_path):
            return home_path

        return None

    def synthesize(self, text: str) -> bytes:
        if not self.service:
             raise TJBotError("Watson TTS not initialized.")

        voice = self.backend_config.voice if self.backend_config else None
        # Provide a default voice if none specified?
        if not voice:
             voice = 'en-US_MichaelV3Voice' # Common default

        try:
            response = self.service.synthesize(
                text,
                voice=voice,
                accept='audio/wav'
            ).get_result()

            return response.content
        except Exception as e:
            logger.error(f"Watson TTS synthesis error: {e}")
            raise TJBotError(f"Watson TTS error: {e}")
