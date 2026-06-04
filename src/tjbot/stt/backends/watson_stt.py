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

from collections.abc import Iterator
from typing import Any, Iterable, Optional, cast
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
    from ibm_watson.websocket import AudioSource, RecognizeCallback
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
except ImportError:
    SpeechToTextV1 = None
    AudioSource = None
    RecognizeCallback = None
    IAMAuthenticator = None

logger = logging.getLogger(__name__)


class _IterableAudioSourceStream:
    """Adapt an iterable of PCM byte chunks to the Watson websocket read() contract."""

    def __init__(self, audio_stream: Iterable[bytes]):
        self._iterator: Iterator[bytes] = iter(audio_stream)
        self._buffer = bytearray()
        self._closed = False

    def read(self, size: int) -> bytes:
        if self._closed:
            return b""

        while len(self._buffer) < size:
            try:
                chunk = next(self._iterator)
            except StopIteration:
                break

            if chunk:
                self._buffer.extend(chunk)

        if not self._buffer:
            return b""

        if size <= 0:
            size = len(self._buffer)

        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def close(self) -> None:
        self._closed = True


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
        speech_to_text_cls = SpeechToTextV1
        authenticator_cls = IAMAuthenticator
        if speech_to_text_cls is None or authenticator_cls is None:
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
                authenticator = authenticator_cls(apikey)
                self.service = speech_to_text_cls(authenticator=authenticator)
                if url:
                    self.service.set_service_url(url)
            else:
                # Auto-load from env/file
                self.service = speech_to_text_cls(authenticator=cast(Any, None))

            logger.info("Watson STT initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Watson STT: {e}")
            raise TJBotError(f"Failed to initialize Watson STT: {e}")

    def transcribe(
        self, audio_stream: Iterable[bytes], options: Optional[STTRequestOptions] = None
    ) -> str:
        callback_base = RecognizeCallback
        if AudioSource is None or callback_base is None:
            raise TJBotError("ibm-watson websocket support is unavailable.")

        if not self.service:
            raise TJBotError("Watson STT not initialized or credentials missing.")

        options = options or {}
        abort_signal = options.get("abort_signal")
        on_partial_result = options.get("on_partial_result")
        on_final_result = options.get("on_final_result")
        stop_stream = options.get("stop_stream")

        self.raise_if_aborted(options)

        # We need to map config to params
        # model, inactivity_timeout, etc.
        model = (
            self.backend_config.model if self.backend_config else "en-US_BroadbandModel"
        )
        inactivity_timeout = (
            self.backend_config.inactivity_timeout
            if (
                self.backend_config
                and self.backend_config.inactivity_timeout is not None
            )
            else -1
        )
        background_audio_suppression = (
            self.backend_config.background_audio_suppression
            if (
                self.backend_config
                and self.backend_config.background_audio_suppression is not None
            )
            else 0.4
        )
        interim_results = (
            self.backend_config.interim_results
            if (self.backend_config and self.backend_config.interim_results is not None)
            else False
        )

        # Audio source: generator
        # content_type: audio/l16; rate=...; channels=...
        # We assume standard 16khz 1channel pcm from microphone usually, but should be configurable.
        content_type = f"audio/l16; rate={self.microphone_rate}; channels={self.microphone_channels}"

        try:
            watson_audio = AudioSource(_IterableAudioSourceStream(audio_stream))

            class _RecognizeCallback(callback_base):
                def __init__(self, engine: "IBMWatsonSTTEngine"):
                    super().__init__()
                    self._engine = engine
                    self.final_parts: list[str] = []
                    self.latest_partial = ""
                    self.error_message: Optional[str] = None
                    self.timeout_like_end = False

                @staticmethod
                def _get_value(source: Any, key: str, default: Any = None) -> Any:
                    if isinstance(source, dict):
                        return source.get(key, default)
                    return getattr(source, key, default)

                @classmethod
                def _extract_text(cls, alternative: Any) -> str:
                    if isinstance(alternative, str):
                        return alternative.strip()
                    text = cls._get_value(alternative, "transcript", "")
                    return str(text).strip() if text else ""

                def _consume_results(self, results: Any) -> None:
                    if self._engine._is_abort_signal_set(abort_signal):
                        return

                    if not results:
                        return

                    result = results[0]
                    alternatives = self._get_value(result, "alternatives") or []
                    if not alternatives:
                        return

                    text = self._extract_text(alternatives[0])
                    if not text:
                        return

                    is_final = bool(self._get_value(result, "final", False))
                    if interim_results and not is_final:
                        self.latest_partial = text
                        if on_partial_result:
                            on_partial_result(text)
                        return

                    if is_final:
                        self.final_parts.append(text)
                        if on_final_result:
                            on_final_result(text)
                        if stop_stream:
                            stop_stream()

                def on_transcription(self, transcript):
                    if not transcript:
                        return

                    # Node handleData: payload.results[0].alternatives[0].transcript
                    # The SDK on_transcription delivers either:
                    #   - a list of alternatives dicts (with "transcript" key)
                    #   - a payload object/dict with .results containing result objects
                    if isinstance(transcript, list):
                        # List of alternatives — treat as single final result
                        text = self._extract_text(transcript[0])
                        if text:
                            self.final_parts.append(text)
                            if on_final_result:
                                on_final_result(text)
                    else:
                        nested_results = self._get_value(transcript, "results")
                        if nested_results:
                            self._consume_results(nested_results)

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
                    results = self._get_value(data, "results")
                    if results:
                        self._consume_results(results)

                def on_close(self):
                    return

            callback = _RecognizeCallback(self)

            self.service.recognize_using_websocket(
                audio=watson_audio,
                content_type=content_type,
                recognize_callback=callback,
                model=model,
                inactivity_timeout=inactivity_timeout,
                background_audio_suppression=background_audio_suppression,
                interim_results=interim_results,
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
            if isinstance(e, TJBotError):
                if e.code != "stt.aborted":
                    logger.error(f"Watson STT Transcribe error: {e}")
                raise
            logger.error(f"Watson STT Transcribe error: {e}")
            raise TJBotError(f"Watson STT error: {e}", cause=e)
