from typing import Any, Iterable, Optional
import logging
from ..stt_engine import STTEngine, STTRequestOptions
from ..stt_utils import (
    is_timeout_like_stream_end_reason,
    resolve_transcript_for_stream_end,
)
from ...config.config_types import STTBackendIBMWatsonConfig
from ...utils.errors import TJBotError
from ...utils.credentials import load_ibm_watson_cloud_credentials

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

    def __init__(self, config: Optional[STTBackendIBMWatsonConfig] = None):
        super().__init__(None)
        self.backend_config = config
        self.service: Any = None
        self.microphone_rate = 44100
        self.microphone_channels = 2

    def initialize(self, microphone_rate: int, microphone_channels: int) -> None:
        if SpeechToTextV1 is None:
            raise TJBotError("ibm-watson library not installed. Please install it.")

        self.microphone_rate = microphone_rate
        self.microphone_channels = microphone_channels

        credentials_path = getattr(self.backend_config, "credentials_path", None) or ""
        load_ibm_watson_cloud_credentials(credentials_path)

        try:
            # SDK automatically asserts env vars like SPEECH_TO_TEXT_APIKEY / URL
            # Or if prompt was using IAMAuthenticator manually...
            # The simplest way with new SDK is let it auto-configure acting on env vars
            # Use authenticator if config has apikey
            apikey = getattr(self.backend_config, "apikey", None)
            url = getattr(self.backend_config, "url", None)

            if apikey:
                authenticator = IAMAuthenticator(apikey)
                self.service = SpeechToTextV1(authenticator=authenticator)
                if url:
                    self.service.set_service_url(url)
            else:
                # Auto-load from env/file
                self.service = SpeechToTextV1(
                    authenticator=None
                )  # SDK might raise if no creds found

            logger.info("Watson STT initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Watson STT: {e}")
            raise TJBotError(f"Failed to initialize Watson STT: {e}")

    def transcribe(
        self, audio_stream: Iterable[bytes], options: Optional[STTRequestOptions] = None
    ) -> str:
        if not self.service:
            raise TJBotError("Watson STT not initialized or credentials missing.")

        options = options or {}
        abort_signal = options.get("abort_signal")
        on_partial_result = options.get("on_partial_result")
        on_final_result = options.get("on_final_result")

        self.raise_if_aborted(options)

        # Watson Python SDK 'recognize_using_websocket' expects a file-like object or generator.
        # audio_stream IS a generator yielding bytes.

        # We need to map config to params
        # model, inactivity_timeout, etc.
        model = (
            self.backend_config.model if self.backend_config else "en-US_BroadbandModel"
        )

        # Audio source: generator
        # content_type: audio/l16; rate=...; channels=...
        # We assume standard 16khz 1channel pcm from microphone usually, but should be configurable.
        content_type = f"audio/l16; rate={self.microphone_rate}; channels={self.microphone_channels}"

        try:

            class _RecognizeCallback:
                def __init__(self, engine: "IBMWatsonSTTEngine"):
                    self._engine = engine
                    self.final_parts: list[str] = []
                    self.latest_partial = ""
                    self.error_message: Optional[str] = None
                    self.timeout_like_end = False

                def on_transcription(self, transcript):
                    if self._engine._is_abort_signal_set(abort_signal):
                        return
                    if not transcript:
                        return

                    results = transcript.get("results")
                    if not results:
                        return

                    for result in results:
                        alternatives = result.get("alternatives") or []
                        if not alternatives:
                            continue

                        text = (alternatives[0].get("transcript") or "").strip()
                        if not text:
                            continue

                        if result.get("final"):
                            self.final_parts.append(text)
                            if on_final_result:
                                on_final_result(text)
                        else:
                            self.latest_partial = text
                            if on_partial_result:
                                on_partial_result(text)

                def on_connected(self):
                    return

                def on_error(self, error):
                    self.error_message = str(error)
                    if is_timeout_like_stream_end_reason(self.error_message):
                        self.timeout_like_end = True

                def on_inactivity_timeout(self, error):
                    self.error_message = str(error)
                    self.timeout_like_end = True

                def on_listening(self):
                    return

                def on_hypothesis(self, hypothesis):
                    _ = hypothesis

                def on_data(self, data):
                    _ = data

                def on_close(self):
                    return

            callback = _RecognizeCallback(self)

            self.service.recognize_using_websocket(
                audio=audio_stream,
                content_type=content_type,
                recognize_callback=callback,
                model=model,
                interim_results=True if on_partial_result else False,
            )

            if self._is_abort_signal_set(abort_signal):
                raise TJBotError(
                    "IBM Watson STT transcription aborted", code="stt.aborted"
                )

            final_transcript = " ".join(callback.final_parts).strip()
            timeout_like_end = (
                callback.timeout_like_end
                or is_timeout_like_stream_end_reason(callback.error_message)
            )
            transcript = resolve_transcript_for_stream_end(
                final_transcript,
                callback.latest_partial,
                allow_partial_on_timeout_like_end=True,
                timeout_like_end=timeout_like_end or not bool(final_transcript),
            )

            if transcript:
                if transcript != final_transcript and on_final_result:
                    on_final_result(transcript)
                return transcript

            if callback.error_message and not timeout_like_end:
                raise TJBotError(
                    "IBM Watson STT recognition failed",
                    cause=RuntimeError(callback.error_message),
                )

            if timeout_like_end:
                raise TJBotError(
                    "IBM Watson STT: No speech could be recognized",
                    code="stt.no-speech",
                )

            raise TJBotError(
                "IBM Watson STT: No speech could be recognized", code="stt.no-speech"
            )

        except Exception as e:
            logger.error(f"Watson STT Transcribe error: {e}")
            if isinstance(e, TJBotError):
                raise
            raise TJBotError(f"Watson STT error: {e}", cause=e)
