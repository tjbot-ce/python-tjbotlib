# Copyright 2026-present TJBot Contributors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any, Iterable, Optional
import logging
import threading
from ..stt_engine import STTEngine, STTRequestOptions
from ..stt_utils import (
    is_timeout_like_stream_end_reason,
    resolve_transcript_for_stream_end,
)
from ...config.config_types import STTBackendAzureConfig
from ...utils.errors import TJBotError
from ...utils.credentials import load_azure_credentials

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None

logger = logging.getLogger(__name__)


def _to_azure_cancellation_error(reason: str, details: str) -> TJBotError:
    cancel_reason = f"{reason} - {details}".strip()
    timeout_like_end = is_timeout_like_stream_end_reason(cancel_reason)
    if timeout_like_end:
        return TJBotError(
            "Azure STT: No speech could be recognized", code="stt.no-speech"
        )
    return TJBotError(f"Azure STT canceled: {cancel_reason}")


class AzureSTTEngine(STTEngine):
    """
    Azure Cognitive Services Speech-to-Text backend.
    """

    def __init__(self, config: Optional[STTBackendAzureConfig] = None):
        super().__init__(None)
        self.backend_config = config
        self.speech_config: Any = None
        self.microphone_rate = 44100
        self.microphone_channels = 2

    def initialize(self, microphone_rate: int, microphone_channels: int) -> None:
        sdk = speechsdk
        if sdk is None:
            raise TJBotError(
                "azure-cognitiveservices-speech library not installed. Please install it."
            )

        self.microphone_rate = microphone_rate
        self.microphone_channels = microphone_channels

        credentials_path = getattr(self.backend_config, "credentials_path", None) or ""
        creds = load_azure_credentials(credentials_path)
        key = creds.get("speechKey") or ""
        region = creds.get("speechRegion") or ""

        if not key or not region:
            raise TJBotError(
                "Azure Speech credentials missing. Provide key and region in azure-credentials.env."
            )

        try:
            self.speech_config = sdk.SpeechConfig(subscription=key, region=region)
            language = self.backend_config.language if self.backend_config else "en-US"
            self.speech_config.speech_recognition_language = language

            logger.info("Azure STT initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Azure STT: {e}")
            raise TJBotError(f"Failed to initialize Azure STT: {e}")

    def transcribe(
        self, audio_stream: Iterable[bytes], options: Optional[STTRequestOptions] = None
    ) -> str:
        sdk = speechsdk
        if sdk is None:
            raise TJBotError(
                "azure-cognitiveservices-speech library not installed. Please install it."
            )

        if not self.speech_config:
            raise TJBotError("Azure STT not initialized.")

        options = options or {}
        abort_signal = options.get("abort_signal")
        on_partial_result = options.get("on_partial_result")
        on_final_result = options.get("on_final_result")
        stop_stream = options.get("stop_stream")
        interim_results = bool(
            getattr(self.backend_config, "interim_results", False)
            if self.backend_config
            else False
        )

        self.raise_if_aborted(options)

        # Handling streaming audio with Azure SDK is done via PushAudioInputStream
        stream_format = sdk.audio.AudioStreamFormat(
            samples_per_second=self.microphone_rate,
            bits_per_sample=16,
            channels=self.microphone_channels,
        )
        push_stream = sdk.audio.PushAudioInputStream(stream_format=stream_format)
        audio_config = sdk.audio.AudioConfig(stream=push_stream)

        recognizer = sdk.SpeechRecognizer(
            speech_config=self.speech_config, audio_config=audio_config
        )

        # Setup events
        done_event = threading.Event()
        final_transcript = []
        latest_partial = ""
        cancellation_reason: Optional[str] = None
        cancellation_details: Optional[str] = None

        def processing_func():
            try:
                for chunk in audio_stream:
                    if self._is_abort_signal_set(abort_signal):
                        break
                    push_stream.write(chunk)
            finally:
                push_stream.close()

        # Start pushing audio in background thread
        push_thread = threading.Thread(target=processing_func)
        push_thread.start()

        # Callbacks
        def recognized_cb(evt):
            if evt.result.reason == sdk.ResultReason.RecognizedSpeech:
                text = evt.result.text
                final_transcript.append(text)
                if on_final_result:
                    on_final_result(text)
                # When not streaming interim results, resolve on the first final result
                # (equivalent to Node's recognizeOnceAsync)
                if not interim_results:
                    done_event.set()

        def recognizing_cb(evt):
            nonlocal latest_partial
            if evt.result.reason == sdk.ResultReason.RecognizingSpeech:
                text = evt.result.text
                if text:
                    latest_partial = text
                if on_partial_result:
                    on_partial_result(text)

        def canceled_cb(evt):
            nonlocal cancellation_reason, cancellation_details
            cancellation_reason = str(evt.reason)
            cancellation_details = str(getattr(evt, "error_details", "") or "")
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
        while not done_event.wait(0.1):
            if self._is_abort_signal_set(abort_signal):
                done_event.set()
                break

        recognizer.stop_continuous_recognition()
        if callable(stop_stream):
            stop_stream()
        push_thread.join(timeout=2.0)

        if self._is_abort_signal_set(abort_signal):
            raise TJBotError("Azure STT transcription aborted", code="stt.aborted")

        transcript = " ".join(final_transcript).strip()
        if transcript:
            return transcript

        if cancellation_reason is not None:
            fallback_transcript = resolve_transcript_for_stream_end(
                transcript,
                latest_partial,
                allow_partial_on_timeout_like_end=True,
                timeout_like_end=is_timeout_like_stream_end_reason(
                    f"{cancellation_reason} - {cancellation_details or ''}"
                ),
            )
            if fallback_transcript:
                if on_final_result:
                    on_final_result(fallback_transcript)
                return fallback_transcript
            raise _to_azure_cancellation_error(
                cancellation_reason, cancellation_details or ""
            )

        fallback_transcript = resolve_transcript_for_stream_end(
            transcript,
            latest_partial,
            allow_partial_on_timeout_like_end=True,
            timeout_like_end=True,
        )
        if fallback_transcript:
            if on_final_result:
                on_final_result(fallback_transcript)
            return fallback_transcript

        if not transcript:
            raise TJBotError(
                "Azure STT: No speech could be recognized", code="stt.no-speech"
            )
        return transcript
