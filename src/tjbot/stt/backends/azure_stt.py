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

from typing import Any, Callable, Iterable, Optional
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
    import azure.cognitiveservices.speech as speechsdk  # type: ignore[import-untyped]
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

        # For non-interim mode, use one-shot recognition (matching Node behavior)
        if not interim_results:
            return self._transcribe_once(
                audio_stream, abort_signal, on_final_result, stop_stream
            )

        # For continuous/interim mode, use continuous recognition
        return self._transcribe_continuous(
            audio_stream, abort_signal, on_partial_result, on_final_result, stop_stream
        )

    def _transcribe_once(
        self,
        audio_stream: Iterable[bytes],
        abort_signal: Optional[object],
        on_final_result: Optional[Callable[[str], None]],
        stop_stream: Optional[Callable[[], None]],
    ) -> str:
        """One-shot recognition for non-interim mode (matching Node's recognizeOnceAsync)."""
        sdk = speechsdk

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

        stop_push_event = threading.Event()
        stream_error: list[Exception] = []

        def processing_func() -> None:
            try:
                for chunk in audio_stream:
                    if stop_push_event.is_set() or self._is_abort_signal_set(
                        abort_signal
                    ):
                        break
                    push_stream.write(chunk)
            except Exception as error:  # pragma: no cover - defensive handling
                stream_error.append(error)
            finally:
                push_stream.close()

        push_thread = threading.Thread(target=processing_func, daemon=True)
        push_thread.start()

        try:
            result = recognizer.recognize_once_async().get()
        finally:
            stop_push_event.set()
            push_thread.join(timeout=0.05)

        if self._is_abort_signal_set(abort_signal):
            if callable(stop_stream):
                stop_stream()
            raise TJBotError("Azure STT transcription aborted", code="stt.aborted")

        if stream_error:
            if callable(stop_stream):
                stop_stream()
            raise TJBotError(
                "Azure STT audio stream error during one-shot transcription",
                cause=stream_error[0],
            )

        return self._handle_recognition_result(
            result,
            on_final_result,
            stop_stream,
        )

    def _transcribe_continuous(
        self,
        audio_stream: Iterable[bytes],
        abort_signal: Optional[object],
        on_partial_result: Optional[Callable[[str], None]],
        on_final_result: Optional[Callable[[str], None]],
        stop_stream: Optional[Callable[[], None]],
    ) -> str:
        """Continuous recognition for interim/streaming mode."""
        sdk = speechsdk

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

    def _handle_recognition_result(
        self,
        result: Any,
        on_final_result: Optional[Callable[[str], None]],
        stop_stream: Optional[Callable[[], None]],
    ) -> str:
        """Handle Azure speech recognition result (for one-shot mode)."""
        sdk = speechsdk

        if result.reason == sdk.ResultReason.RecognizedSpeech:
            if on_final_result:
                on_final_result(result.text)
            if callable(stop_stream):
                stop_stream()
            return result.text.strip()
        elif result.reason == sdk.ResultReason.NoMatch:
            if callable(stop_stream):
                stop_stream()
            raise TJBotError(
                "Azure STT: No speech could be recognized", code="stt.no-speech"
            )
        elif result.reason == sdk.ResultReason.Canceled:
            cancellation = sdk.CancellationDetails.from_result(result)
            if callable(stop_stream):
                stop_stream()
            raise TJBotError(
                f"Azure STT canceled: {cancellation.reason} - {cancellation.error_details}"
            )
        else:
            if callable(stop_stream):
                stop_stream()
            raise TJBotError(
                f"Azure STT recognition failed with reason: {result.reason}"
            )
