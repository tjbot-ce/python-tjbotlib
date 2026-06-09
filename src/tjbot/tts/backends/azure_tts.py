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

import logging
from typing import Any, Optional

from ...config.config_types import TTSBackendAzureConfig
from ...utils.credentials import load_azure_credentials
from ...utils.errors import TJBotError
from ..tts_engine import TTSEngine

try:
    import azure.cognitiveservices.speech as speechsdk  # type: ignore[import-untyped]
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

    def initialize(self) -> None:
        sdk = speechsdk
        if sdk is None:
            raise TJBotError(
                "azure-cognitiveservices-speech library not installed. Please install it."
            )

        voice = self.backend_config.voice if self.backend_config else None
        if not voice:
            raise TJBotError(
                "Azure TTS voice not specified. Provide voice in speak.backend.azure-tts config."
            )

        credentials_path = getattr(self.backend_config, "credentials_path", None) or ""
        creds = load_azure_credentials(credentials_path)
        self.subscription_key = creds.get("speechKey") or ""
        self.region = creds.get("speechRegion") or ""

        if not self.subscription_key or not self.region:
            raise TJBotError(
                "Azure Speech credentials missing. Provide key and region in azure-credentials.env."
            )

        try:
            self.speech_config = sdk.SpeechConfig(
                subscription=self.subscription_key, region=self.region
            )
            logger.info("Azure TTS initialized")
        except Exception as e:
            logger.error("Failed to initialize Azure TTS: %s", e)
            raise TJBotError(f"Failed to initialize Azure TTS: {e}")

    def synthesize(self, text: str) -> bytes:
        sdk = speechsdk
        if sdk is None:
            raise TJBotError(
                "azure-cognitiveservices-speech library not installed. Please install it."
            )

        if not self.speech_config or not self.subscription_key or not self.region:
            raise TJBotError("Azure TTS not initialized. Call initialize() first.")

        self.validate_text(text)

        voice_name = getattr(self.backend_config, "voice", None)
        if not voice_name:
            raise TJBotError(
                "Azure TTS voice not specified. Provide voice in speak config."
            )

        self.speech_config.speech_synthesis_voice_name = voice_name
        self.speech_config.set_speech_synthesis_output_format(
            sdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
        )

        synthesizer = sdk.SpeechSynthesizer(
            speech_config=self.speech_config, audio_config=None
        )

        try:
            result: Any = synthesizer.speak_text_async(text).get()

            if result.reason == sdk.ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            elif result.reason == sdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                raise TJBotError(
                    f"Azure TTS canceled: {cancellation_details.reason} - {cancellation_details.error_details}"
                )
            else:
                raise TJBotError(
                    f"Azure TTS synthesis failed with reason: {result.reason}"
                )

        except Exception as e:
            logger.error("Azure TTS synthesis error: %s", e)
            if isinstance(e, TJBotError):
                raise
            raise TJBotError("Azure TTS synthesis failed", cause=e)
