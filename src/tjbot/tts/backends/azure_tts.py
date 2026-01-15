import os
import logging
from typing import Optional
from ..engine import TTSEngine
from ...config.models import AzureTTSConfig
from ...error import TJBotError

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None

logger = logging.getLogger(__name__)

class AzureTTSEngine(TTSEngine):
    """
    Azure Text-to-Speech backend.
    """
    def __init__(self, config: Optional[AzureTTSConfig] = None):
        self.backend_config = config
        self.speech_config = None
        self._initialize()

    def _initialize(self):
        if speechsdk is None:
             raise TJBotError("azure-cognitiveservices-speech library not installed. Please install it.")

        region = self.backend_config.region if self.backend_config else None
        key = self.backend_config.key if self.backend_config else None

        if not key:
            key = os.environ.get('AZURE_SPEECH_KEY')
        if not region:
            region = os.environ.get('AZURE_SPEECH_REGION')

        if not key or not region:
             raise TJBotError("Azure Speech credentials missing. Set 'key' and 'region' in config or env vars AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.")

        try:
            self.speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
            logger.info("Azure TTS initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Azure TTS: {e}")

    def synthesize(self, text: str) -> bytes:
        if not self.speech_config:
             raise TJBotError("Azure TTS not initialized.")

        # Configure voice
        voice_name = self.backend_config.voiceName if self.backend_config else 'en-US-JennyNeural'
        self.speech_config.speech_synthesis_voice_name = voice_name
        # self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm)

        # Pull stream (memory)
        # pull_stream = speechsdk.audio.PullAudioOutputStream(
        #      speechsdk.audio.PullAudioOutputStream.MemoryStream()
        # )

        # We want to get the bytes simply.
        # SpeechSynthesizer can output to AudioConfig(filename=None) which means default speaker,
        # or we want to capture it.
        # Simplest way in Python API to get bytes:
        # synthesizer.speak_text_async(text).get() -> result -> audio_data

        synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)

        try:
            result = synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                raise TJBotError(f"Azure TTS canceled: {cancellation_details.reason} - {cancellation_details.error_details}")
            else:
                 raise TJBotError(f"Azure TTS failed: {result.reason}")

        except Exception as e:
            logger.error(f"Azure TTS synthesis error: {e}")
            raise TJBotError(f"Azure TTS error: {e}")
