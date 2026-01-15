from typing import Iterator, Callable, Optional
import os
import logging
import threading
from ..engine import STTEngine
from ...config.models import AzureSTTConfig
from ...error import TJBotError

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None

logger = logging.getLogger(__name__)

class AzureSTTEngine(STTEngine):
    """
    Azure Cognitive Services Speech-to-Text backend.
    """
    def __init__(self, config: Optional[AzureSTTConfig] = None):
        self.backend_config = config
        self.speech_config = None
        self._initialize()

    def _initialize(self):
        if speechsdk is None:
             raise TJBotError("azure-cognitiveservices-speech library not installed. Please install it.")

        # Credentials mapping
        # SDK expects AZURE_SPEECH_KEY and AZURE_SPEECH_REGION if provided via env,
        # or we manually construct config.

        region = self.backend_config.region if self.backend_config else None
        key = self.backend_config.key if self.backend_config else None

        # Fallback to env
        if not key:
            key = os.environ.get('AZURE_SPEECH_KEY')
        if not region:
            region = os.environ.get('AZURE_SPEECH_REGION')

        if not key or not region:
             raise TJBotError("Azure Speech credentials missing. Set 'key' and 'region' in config or env vars AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.")

        try:
            self.speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
            # Default language
            language = self.backend_config.language if self.backend_config else 'en-US'
            self.speech_config.speech_recognition_language = language

            logger.info("Azure STT initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Azure STT: {e}")

    def transcribe(
        self,
        audio_stream: Iterator[bytes],
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> str:
        if not self.speech_config:
             raise TJBotError("Azure STT not initialized.")

        # Handling streaming audio with Azure SDK is done via PushAudioInputStream
        stream_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
        push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
        audio_config = speechsdk.audio.AudioConfig(stream_input=push_stream)

        recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=audio_config)

        # Setup events
        done_event = threading.Event()
        final_transcript = []

        def processing_func():
            try:
                for chunk in audio_stream:
                    push_stream.write(chunk)
            finally:
                push_stream.close()

        # Start pushing audio in background thread
        push_thread = threading.Thread(target=processing_func)
        push_thread.start()

        # Callbacks
        def recognized_cb(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                text = evt.result.text
                final_transcript.append(text)
                if on_final_result:
                    on_final_result(text)

        def recognizing_cb(evt):
             if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
                 text = evt.result.text
                 if on_partial_result:
                     on_partial_result(text)

        def canceled_cb(evt):
            if evt.reason == speechsdk.CancellationReason.Error:
                if on_error:
                    on_error(Exception(f"Azure Cancelled: {evt.error_details}"))
            done_event.set()

        def session_stopped_cb(evt):
            done_event.set()

        recognizer.recognized.connect(recognized_cb)
        recognizer.recognizing.connect(recognizing_cb)
        recognizer.canceled.connect(canceled_cb)
        recognizer.session_stopped.connect(session_stopped_cb)

        # Start continuous recognition
        recognizer.start_continuous_recognition()

        # Wait for done (which happens when stream closes/stops)
        done_event.wait()

        recognizer.stop_continuous_recognition()
        push_thread.join()

        return " ".join(final_transcript)
