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

import os
from typing import Any, Iterable, Iterator, Optional

import logging
from ..stt_engine import STTEngine, STTRequestOptions
from ..stt_utils import (
    is_timeout_like_stream_end_reason,
    resolve_transcript_for_stream_end,
)
from ...config.config_types import STTBackendGoogleCloudConfig
from ...utils.errors import TJBotError
from ...utils.credentials import load_google_cloud_credentials

try:
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech as cs
except ImportError:
    SpeechClient = None  # type: ignore[assignment,misc]
    cs = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_SUPPORTED_GOOGLE_STT_MODEL_REGIONS: dict[str, list[str]] = {
    "chirp_3": ["us", "eu"],
    "chirp_2": ["us-central1", "europe-west4", "asia-southeast1"],
}

_MAX_AUDIO_CHUNK_BYTES = 25600


def _resolve_google_project_id() -> str:
    env_project_id = (
        os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT") or ""
    ).strip()
    if env_project_id:
        return env_project_id

    try:
        from google.auth import default as google_auth_default

        _, project_id = google_auth_default()
        return (project_id or "").strip()
    except Exception:
        return ""


def _assert_supported_model_and_region(model: str, region: str) -> None:
    if model not in _SUPPORTED_GOOGLE_STT_MODEL_REGIONS:
        supported = ", ".join(_SUPPORTED_GOOGLE_STT_MODEL_REGIONS)
        raise TJBotError(
            f'Google Cloud STT model "{model}" is not supported. Supported models: {supported}'
        )
    supported_regions = _SUPPORTED_GOOGLE_STT_MODEL_REGIONS[model]
    if region not in supported_regions:
        raise TJBotError(
            f'Google Cloud STT region "{region}" is not supported for model "{model}". '
            f"Supported regions: {', '.join(supported_regions)}"
        )


def _to_google_cloud_recognition_error(
    error: Exception, recognizer_path: str
) -> TJBotError:
    code = getattr(error, "code", None)
    code_value = code() if callable(code) else code
    reason = getattr(error, "reason", None)
    details = getattr(error, "details", None) or str(error)
    details_lower = details.lower()
    code_text = str(code_value).lower()
    reason_text = str(reason).lower()

    is_audio_chunk_too_large = "25600" in details_lower and "bytes" in details_lower
    is_permission_denied = (
        "permission_denied" in code_text
        or code_text == "7"
        or "iam_permission_denied" in reason_text
        or "permission denied" in details_lower
    )

    if is_audio_chunk_too_large:
        return TJBotError(
            f"Google Cloud STT rejected an audio chunk over {_MAX_AUDIO_CHUNK_BYTES} bytes. "
            "Audio must be streamed in smaller chunks.",
            code="stt.google-cloud.chunk-too-large",
            context={
                "recognizer": recognizer_path,
                "details": details,
            },
            cause=error,
        )

    if is_permission_denied:
        return TJBotError(
            (
                f"Google Cloud STT permission denied for recognizer {recognizer_path}. "
                "Ensure credentials include speech.recognizers.recognize on the recognizer "
                "and region matches the recognizer location."
            ),
            code="stt.google-cloud.permission-denied",
            context={
                "recognizer": recognizer_path,
                "details": details,
            },
            cause=error,
        )

    return TJBotError(
        "Google Cloud STT recognition failed",
        context={
            "recognizer": recognizer_path,
            "details": details,
        },
        cause=error,
    )


class GoogleCloudSTTEngine(STTEngine):
    """
    Google Cloud Speech-to-Text v2 backend (chirp_2 / chirp_3 models).
    """

    def __init__(
        self,
        config: Optional[STTBackendGoogleCloudConfig] = None,
    ):
        super().__init__(None)
        self.backend_config = config
        self.microphone_rate = 44100
        self.microphone_channels = 2
        self.client: Any = None
        self.project_id = ""

    def initialize(self, microphone_rate: int, microphone_channels: int) -> None:
        if SpeechClient is None:
            raise TJBotError(
                "google-cloud-speech library not installed. Please install it."
            )

        self.microphone_rate = microphone_rate
        self.microphone_channels = microphone_channels

        cfg = self.backend_config
        model = (cfg.model or "").strip() if cfg else ""
        language_code = (cfg.language_code or "").strip() if cfg else ""
        region = (cfg.region or "").strip() if cfg else ""

        if not model:
            raise TJBotError(
                "Google Cloud STT model not specified. Provide model in listen.backend.google-cloud-stt config."
            )
        if not language_code:
            raise TJBotError(
                "Google Cloud STT languageCode not specified. Provide languageCode in listen.backend.google-cloud-stt config."
            )
        if not region:
            raise TJBotError(
                "Google Cloud STT region not specified. Provide region in listen.backend.google-cloud-stt config."
            )

        _assert_supported_model_and_region(model, region)

        credentials_path = (cfg.credentials_path or "") if cfg else ""
        load_google_cloud_credentials(credentials_path)
        self.project_id = _resolve_google_project_id()
        if not self.project_id:
            raise TJBotError(
                "Google Cloud project_id could not be determined. Set GOOGLE_CLOUD_PROJECT/GCLOUD_PROJECT or provide credentials discoverable via Application Default Credentials."
            )

        endpoint = f"{region}-speech.googleapis.com"
        try:
            self.client = SpeechClient(client_options={"api_endpoint": endpoint})
            logger.info(
                "Google Cloud STT v2 initialized (model=%s, region=%s)", model, region
            )
        except Exception as e:
            logger.error("Failed to initialize Google Cloud STT v2: %s", e)
            raise TJBotError(f"Failed to initialize Google Cloud STT v2: {e}")

    def transcribe(
        self, audio_stream: Iterable[bytes], options: Optional[STTRequestOptions] = None
    ) -> str:
        if not self.client:
            raise TJBotError("Google Cloud STT client not initialized.")

        options = options or {}
        abort_signal = options.get("abort_signal")
        on_partial_result = options.get("on_partial_result")
        on_final_result = options.get("on_final_result")

        self.raise_if_aborted(options)

        cfg = self.backend_config
        model = (cfg.model or "").strip() if cfg else ""
        language_code = (cfg.language_code or "").strip() if cfg else ""
        region = (cfg.region or "").strip() if cfg else ""
        enable_automatic_punctuation: bool = (
            cfg.enable_automatic_punctuation
            if (cfg and cfg.enable_automatic_punctuation is not None)
            else True
        )
        profanity_filter: bool = (
            cfg.profanity_filter if (cfg and cfg.profanity_filter is not None) else True
        )
        interim_results: bool = (
            cfg.interim_results if (cfg and cfg.interim_results is not None) else True
        )

        recognizer_path = f"projects/{self.project_id}/locations/{region}/recognizers/_"

        logger.debug(
            "Transcribing with Google Cloud STT v2 (model=%s, language=%s, recognizer=%s)",
            model,
            language_code,
            recognizer_path,
        )

        streaming_config = cs.StreamingRecognitionConfig(
            config=cs.RecognitionConfig(
                explicit_decoding_config=cs.ExplicitDecodingConfig(
                    encoding=cs.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=self.microphone_rate,
                    audio_channel_count=self.microphone_channels,
                ),
                model=model,
                language_codes=[language_code],
                features=cs.RecognitionFeatures(
                    enable_automatic_punctuation=enable_automatic_punctuation,
                    profanity_filter=profanity_filter,
                ),
            ),
            streaming_features=cs.StreamingRecognitionFeatures(
                interim_results=interim_results,
            ),
        )

        def _request_generator() -> Iterator[cs.StreamingRecognizeRequest]:
            yield cs.StreamingRecognizeRequest(
                recognizer=recognizer_path,
                streaming_config=streaming_config,
            )
            for chunk in audio_stream:
                if self._is_abort_signal_set(abort_signal):
                    raise TJBotError(
                        "Google Cloud STT transcription aborted", code="stt.aborted"
                    )
                # Chunk audio to stay within 25600-byte API limit
                for offset in range(0, len(chunk), _MAX_AUDIO_CHUNK_BYTES):
                    yield cs.StreamingRecognizeRequest(
                        audio=chunk[offset : offset + _MAX_AUDIO_CHUNK_BYTES],
                    )

        latest_partial = ""
        final_transcript = ""

        try:
            responses = self.client.streaming_recognize(requests=_request_generator())

            for response in responses:
                if self._is_abort_signal_set(abort_signal):
                    raise TJBotError(
                        "Google Cloud STT transcription aborted", code="stt.aborted"
                    )
                if not response.results:
                    continue
                result = response.results[0]
                if not result.alternatives:
                    continue

                transcript = (result.alternatives[0].transcript or "").strip()
                if not transcript:
                    continue

                if not result.is_final:
                    latest_partial = transcript
                    if on_partial_result:
                        on_partial_result(transcript)
                else:
                    final_transcript = transcript
                    latest_partial = ""
                    if on_final_result:
                        on_final_result(transcript)

            transcript = final_transcript or latest_partial
            if not transcript:
                raise TJBotError(
                    "Google Cloud STT: No speech could be recognized",
                    code="stt.no-speech",
                )
            return transcript

        except Exception as e:
            logger.error("Google Cloud STT v2 error: %s", e)
            if isinstance(e, TJBotError):
                raise

            timeout_like_stream_end = is_timeout_like_stream_end_reason(str(e))
            fallback_transcript = resolve_transcript_for_stream_end(
                final_transcript,
                latest_partial,
                allow_partial_on_timeout_like_end=True,
                timeout_like_end=timeout_like_stream_end,
            )
            if fallback_transcript:
                if fallback_transcript != final_transcript and on_final_result:
                    on_final_result(fallback_transcript)
                return fallback_transcript

            if timeout_like_stream_end:
                raise TJBotError(
                    "Google Cloud STT: No speech could be recognized",
                    code="stt.no-speech",
                )

            raise _to_google_cloud_recognition_error(e, recognizer_path)
