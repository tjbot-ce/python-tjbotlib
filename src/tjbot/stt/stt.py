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
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional

from ..config.config_types import ListenConfig
from ..utils.errors import TJBotError
from .stt_engine import STTEngine, STTRequestOptions, create_stt_engine

if TYPE_CHECKING:
    from ..microphone import MicrophoneController

logger = logging.getLogger(__name__)


class STTController:
    """STT controller that manages transcription engine lifecycle."""

    def __init__(
        self,
        listen_config: Optional[ListenConfig] = None,
        microphone_controller: Optional["MicrophoneController"] = None,
    ):
        self.config: Optional[ListenConfig] = None
        self.engine: Optional[STTEngine] = None
        self.microphone_controller = microphone_controller

        if listen_config is not None:
            self.initialize(listen_config)

    def initialize(self, listen_config: ListenConfig) -> None:
        self.config = listen_config
        self.engine = create_stt_engine(listen_config)

        microphone_rate = listen_config.microphone_rate or 44100
        microphone_channels = listen_config.microphone_channels or 2
        self.engine.initialize(microphone_rate, microphone_channels)

    def _is_no_speech_error(self, error: Exception) -> bool:
        return isinstance(error, TJBotError) and error.code == "stt.no-speech"

    def transcribe(
        self,
        audio_stream: Optional[Iterable[bytes]] = None,
        *,
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
        abort_signal: Any = None,
    ) -> str:
        if self.config is None or self.engine is None:
            raise TJBotError(
                "STT engine not initialized. Call initialize() before transcribing."
            )

        options: STTRequestOptions = {
            "on_partial_result": on_partial_result,
            "on_final_result": on_final_result,
            "abort_signal": abort_signal,
        }

        self.engine.raise_if_aborted(options)

        # If caller supplies an audio stream, use it directly
        if audio_stream is not None:
            return self.engine.transcribe(audio_stream, options)

        # Otherwise, use the microphone controller with retry on no-speech
        if self.microphone_controller is None:
            raise TJBotError(
                "Microphone controller is not available for STT transcription."
            )

        while True:
            self.microphone_controller.start()
            active_stream = self.microphone_controller.get_input_stream()

            def _stop_streaming(_stream=active_stream) -> None:
                _stream.stop()
                self.microphone_controller.pause()

            options["stop_stream"] = _stop_streaming

            try:
                transcript = self.engine.transcribe(active_stream, options)
                logger.debug("Transcript: %s", transcript)
                return transcript
            except Exception as error:
                if self._is_no_speech_error(error):
                    self.engine.raise_if_aborted(options)
                    logger.debug("No speech detected; continuing to listen")
                    continue
                raise
            finally:
                self.microphone_controller.pause()

    def cleanup(self) -> None:
        if self.engine is not None:
            self.engine.cleanup()
            self.engine = None
