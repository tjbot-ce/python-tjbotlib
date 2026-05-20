import logging
from typing import Optional
from ..tts_engine import TTSEngine
from ...config.config_types import TTSBackendAzureConfig
from ...utils.errors import TJBotError
from ...utils.credentials import load_azure_credentials

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None

logger = logging.getLogger(__name__)

class AzureTTSEngine(TTSEngine):
    """
    Azure Text-to-Speech backend.
    """
    def __init__(self, config: Optional[TTSBackendAzureConfig] = None):
        super().__init__(config.model_dump(by_alias=True) if config else {})
        self.backend_config = config
        self.speech_config = None
        self.subscription_key: Optional[str] = None
        self.region: Optional[str] = None

    async def initialize(self) -> None:
        if speechsdk is None:
            raise TJBotError('azure-cognitiveservices-speech library not installed. Please install it.')

        voice = self.backend_config.voice if self.backend_config else None
        if not voice:
            raise TJBotError('Azure TTS voice not specified. Provide voice in speak.backend.azure-tts config.')

        credentials_path = getattr(self.backend_config, 'credentials_path', None) or ''
        creds = load_azure_credentials(credentials_path)
        self.subscription_key = creds.get('speechKey') or ''
        self.region = creds.get('speechRegion') or ''

        if not self.subscription_key or not self.region:
            raise TJBotError('Azure Speech credentials missing. Provide key and region in azure-credentials.env.')

        try:
            self.speech_config = speechsdk.SpeechConfig(subscription=self.subscription_key, region=self.region)
            logger.info('Azure TTS initialized')
        except Exception as e:
            logger.error('Failed to initialize Azure TTS: %s', e)
            raise TJBotError(f'Failed to initialize Azure TTS: {e}')

    async def synthesize(self, text: str) -> bytes:
        if not self.speech_config or not self.subscription_key or not self.region:
            raise TJBotError('Azure TTS not initialized. Call initialize() first.')

        self.validate_text(text)

        voice_name = getattr(self.backend_config, 'voice', None)
        if not voice_name:
            raise TJBotError('Azure TTS voice not specified. Provide voice in speak config.')

        self.speech_config.speech_synthesis_voice_name = voice_name
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
        )

        synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)

        try:
            result = synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                raise TJBotError(f'Azure TTS canceled: {cancellation_details.reason} - {cancellation_details.error_details}')
            else:
                raise TJBotError(f'Azure TTS synthesis failed with reason: {result.reason}')

        except Exception as e:
            logger.error('Azure TTS synthesis error: %s', e)
            if isinstance(e, TJBotError):
                raise
            raise TJBotError('Azure TTS synthesis failed', cause=e)
