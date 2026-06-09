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

from ..tts_engine import TTSEngine
from ...config.config_types import TTSBackendGoogleCloudConfig
from ...utils.errors import TJBotError
from ...utils.credentials import load_google_cloud_credentials

try:
    from google.cloud import texttospeech
except ImportError:
    texttospeech = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class GoogleCloudTTSEngine(TTSEngine):
    """
    Google Cloud Text-to-Speech backend.
    """

    def __init__(self, config: Optional[TTSBackendGoogleCloudConfig] = None):
        super().__init__(config.model_dump(by_alias=True) if config else {})
        self.backend_config = config
        self.client: Any = None

    def initialize(self) -> None:
        sdk = texttospeech
        if sdk is None:
            raise TJBotError(
                "google-cloud-texttospeech library not installed. Please install it."
            )

        voice = self.backend_config.voice if self.backend_config else None
        language_code = (
            self.backend_config.language_code if self.backend_config else None
        )
        if not voice:
            raise TJBotError(
                "Google Cloud TTS voice not specified. Provide voice in speak.backend.google-cloud-tts config."
            )
        if not language_code:
            raise TJBotError(
                "Google Cloud TTS languageCode not specified. Provide languageCode in speak.backend.google-cloud-tts config."
            )

        credentials_path = getattr(self.backend_config, "credentials_path", None) or ""
        load_google_cloud_credentials(credentials_path)

        try:
            self.client = sdk.TextToSpeechClient()
            logger.info("Google TTS initialized")
        except Exception as e:
            logger.error("Failed to initialize Google TTS: %s", e)
            raise TJBotError(f"Failed to initialize Google TTS: {e}")

    def synthesize(self, text: str) -> bytes:
        sdk = texttospeech
        if sdk is None:
            raise TJBotError(
                "google-cloud-texttospeech library not installed. Please install it."
            )

        if not self.client:
            raise TJBotError(
                "Google Cloud TTS client not initialized. Call initialize() first."
            )

        self.validate_text(text)

        language_code = (
            self.backend_config.language_code if self.backend_config else "en-US"
        )
        voice_name = self.backend_config.voice if self.backend_config else None
        if not voice_name:
            raise TJBotError(
                "Google Cloud TTS voice not specified. Provide voice in speak config."
            )

        voice = sdk.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        )

        audio_config = sdk.AudioConfig(
            audio_encoding=sdk.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000,
        )

        synthesis_input = sdk.SynthesisInput(text=text)

        try:
            response = self.client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            if not response.audio_content:
                raise TJBotError("No audio data returned from Google Cloud TTS")

            audio_content = bytes(response.audio_content)
            return self._add_wav_header(audio_content, 24000, 1, 16)
        except Exception as e:
            logger.error("Google TTS synthesis error: %s", e)
            if isinstance(e, TJBotError):
                raise
            raise TJBotError("Google Cloud TTS synthesis failed", cause=e)

    def _add_wav_header(
        self, pcm_data: bytes, sample_rate: int, num_channels: int, bits_per_sample: int
    ) -> bytes:
        block_align = (num_channels * bits_per_sample) // 8
        byte_rate = sample_rate * block_align
        data_size = len(pcm_data)
        file_size = 36 + data_size

        header = bytearray(44)
        header[0:4] = b"RIFF"
        header[4:8] = file_size.to_bytes(4, byteorder="little", signed=False)
        header[8:12] = b"WAVE"
        header[12:16] = b"fmt "
        header[16:20] = (16).to_bytes(4, byteorder="little", signed=False)
        header[20:22] = (1).to_bytes(2, byteorder="little", signed=False)
        header[22:24] = num_channels.to_bytes(2, byteorder="little", signed=False)
        header[24:28] = sample_rate.to_bytes(4, byteorder="little", signed=False)
        header[28:32] = byte_rate.to_bytes(4, byteorder="little", signed=False)
        header[32:34] = block_align.to_bytes(2, byteorder="little", signed=False)
        header[34:36] = bits_per_sample.to_bytes(2, byteorder="little", signed=False)
        header[36:40] = b"data"
        header[40:44] = data_size.to_bytes(4, byteorder="little", signed=False)

        return bytes(header) + pcm_data


__all__ = ["GoogleCloudTTSEngine"]
