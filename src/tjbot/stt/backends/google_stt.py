from typing import Iterator, Callable, Optional
import os
import logging
from ..engine import STTEngine
from ...config.models import GoogleCloudSTTConfig
from ...error import TJBotError

try:
    from google.cloud import speech
except ImportError:
    speech = None

logger = logging.getLogger(__name__)

class GoogleCloudSTTEngine(STTEngine):
    """
    Google Cloud Speech-to-Text backend.
    """
    def __init__(self, config: Optional[GoogleCloudSTTConfig] = None):
        self.backend_config = config
        self.client = None
        self._initialize()

    def _initialize(self):
        if speech is None:
             raise TJBotError("google-cloud-speech library not installed. Please install it.")

        # Google Cloud SDK standard auth: GOOGLE_APPLICATION_CREDENTIALS
        if self.backend_config and self.backend_config.keyFilename:
             os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.backend_config.keyFilename

        try:
            self.client = speech.SpeechClient()
            logger.info("Google STT initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google STT: {e}")

    def transcribe(
        self,
        audio_stream: Iterator[bytes],
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> str:
        if not self.client:
             raise TJBotError("Google STT not initialized.")

        # Config mapping
        language_code = self.backend_config.languageCode if self.backend_config else 'en-US'

        # Generator wrapper to yield request objects
        def request_generator():
            # First request contains config
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000, # Should assume 16k or config? Node assumes 16k usually.
                language_code=language_code,
            )
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True if on_partial_result else False
            )

            yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)

            # Subsequent requests contain audio
            for chunk in audio_stream:
                yield speech.StreamingRecognizeRequest(audio_content=chunk)

        try:
            responses = self.client.streaming_recognize(request_generator())

            final_transcript = ""

            for response in responses:
                if not response.results:
                    continue

                result = response.results[0]
                if not result.alternatives:
                    continue

                transcript = result.alternatives[0].transcript

                if result.is_final:
                    final_transcript += transcript
                    if on_final_result:
                        on_final_result(transcript)
                else:
                    if on_partial_result:
                        on_partial_result(transcript)

            return final_transcript

        except Exception as e:
            logger.error(f"Google STT error: {e}")
            if on_error:
                on_error(e)
            raise TJBotError(f"Google STT error: {e}")
