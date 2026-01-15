from typing import Iterator, Callable, Optional
import os
import logging
from ..engine import STTEngine
from ...config.models import IBCWatsonSTTConfig
from ...error import TJBotError

try:
    from ibm_watson import SpeechToTextV1
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
except ImportError:
    SpeechToTextV1 = None
    IAMAuthenticator = None

logger = logging.getLogger(__name__)

class IBMWatsonSTTEngine(STTEngine):
    """
    IBM Watson Speech-to-Text backend.
    """
    def __init__(self, config: Optional[IBCWatsonSTTConfig] = None):
        # We might receive the specific backend config here,
        # or we might need to look it up from environment/files if not provided fully.
        self.backend_config = config
        self.service = None
        self._initialize()

    def _initialize(self):
        if SpeechToTextV1 is None:
             raise TJBotError("ibm-watson library not installed. Please install it.")

        # Try to find credentials
        # Node implementation looks for ibm-credentials.env in CWD or ~/.tjbot/
        # Python SDK handles ibm-credentials.env automatically if present in CWD.
        # But we should also check ~/.tjbot/ location manually if desired to match Node behavior exactly.

        creds_path = self._find_credentials()
        if creds_path:
             os.environ['IBM_CREDENTIALS_FILE'] = creds_path

        try:
            # SDK automatically asserts env vars like SPEECH_TO_TEXT_APIKEY / URL
            # Or if prompt was using IAMAuthenticator manually...
            # The simplest way with new SDK is let it auto-configure acting on env vars
            # Use authenticator if config has apikey
            if self.backend_config and self.backend_config.apikey:
                 authenticator = IAMAuthenticator(self.backend_config.apikey)
                 self.service = SpeechToTextV1(authenticator=authenticator)
                 if self.backend_config.url:
                     self.service.set_service_url(self.backend_config.url)
            else:
                 # Auto-load from env/file
                 self.service = SpeechToTextV1(authenticator=None) # SDK might raise if no creds found

            logger.info("Watson STT initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Watson STT: {e}")
            # Don't raise here, allow lazy failure? Or raise?
            # Node raises.
            pass

    def _find_credentials(self) -> Optional[str]:
        # Check explicit path in config
        if self.backend_config and self.backend_config.credentialsPath:
             return self.backend_config.credentialsPath

        # Check CWD
        cwd_path = os.path.join(os.getcwd(), 'ibm-credentials.env')
        if os.path.exists(cwd_path):
            return cwd_path

        # Check ~/.tjbot/
        home_path = os.path.expanduser('~/.tjbot/ibm-credentials.env')
        if os.path.exists(home_path):
            return home_path

        return None

    def transcribe(
        self,
        audio_stream: Iterator[bytes],
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> str:
        if not self.service:
             raise TJBotError("Watson STT not initialized or credentials missing.")

        # Watson Python SDK 'recognize_using_websocket' expects a file-like object or generator.
        # audio_stream IS a generator yielding bytes.

        # We need to map config to params
        # model, inactivity_timeout, etc.
        model = self.backend_config.model if self.backend_config else 'en-US_BroadbandModel'

        # Audio source: generator
        # content_type: audio/l16; rate=...; channels=...
        # We assume standard 16khz 1channel pcm from microphone usually, but should be configurable.
        content_type = "audio/l16; rate=16000; channels=1"

        try:
            # Note: recognize_using_websocket is blocking?
            # In Python SDK it usually is for file/generator.
            # It returns complex structure.

            # NOTE: ibm-watson Python SDK websocket support might be tricky with generators.
            # Usually it uses a callback class.

            class MyRecognizeCallback:
                def __init__(self):
                    self.final_transcript = ""

                def on_transcription(self, transcript):
                    # logic to parse transcript
                    if not transcript:
                        return
                    results = transcript.get('results')
                    if not results:
                        return

                    for res in results:
                        text = res['alternatives'][0]['transcript']
                        final = res['final']
                        if final:
                            self.final_transcript += text
                            if on_final_result:
                                on_final_result(text)
                        else:
                            if on_partial_result:
                                on_partial_result(text)

                def on_connected(self):
                    pass
                def on_error(self, error):
                    if on_error:
                        on_error(Exception(error))
                def on_inactivity_timeout(self, error):
                    if on_error:
                        on_error(Exception("Inactivity Timeout"))
                def on_listening(self):
                    pass
                def on_hypothesis(self, hypothesis):
                    pass
                def on_data(self, data):
                    pass
                def on_close(self):
                    pass

            callback = MyRecognizeCallback()

            self.service.recognize_using_websocket(
                audio=audio_stream,
                content_type=content_type,
                recognize_callback=callback,
                model=model,
                interim_results=True if on_partial_result else False
            )

            return callback.final_transcript

        except Exception as e:
            logger.error(f"Watson STT Transcribe error: {e}")
            if on_error:
                on_error(e)
            raise TJBotError(f"Watson STT error: {e}")
