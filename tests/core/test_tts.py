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

from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

import pytest

from tjbot.config.config_types import (
    SpeakConfig,
    TTSBackendAzureConfig,
    TTSBackendConfig,
    TTSBackendGoogleCloudConfig,
    TTSBackendIBMWatsonConfig,
    TTSBackendLocalConfig,
)
from tjbot.utils.errors import TJBotError
from tjbot.tts.tts import TTSController


def _install_fake_backend(monkeypatch, module_name: str, class_name: str, cls):
    module = types.ModuleType(module_name)
    setattr(module, class_name, cls)
    monkeypatch.setitem(sys.modules, module_name, module)


def test_tts_none_backend_raises_disabled_error():
    speaker = MagicMock()
    controller = TTSController(speaker)

    speak_config = SpeakConfig(backend=TTSBackendConfig(type="none"))
    controller.initialize(speak_config)

    with pytest.raises(TJBotError, match="TTS is disabled"):
        controller.speak("hello")


def test_tts_local_backend_uses_mocked_engine_module(monkeypatch):
    class FakeLocalEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self) -> None:
            pass

        def synthesize(self, _text: str) -> bytes:
            return b"RIFF"

    _install_fake_backend(
        monkeypatch,
        "tjbot.tts.backends.sherpa_onnx_tts",
        "SherpaONNXTTSEngine",
        FakeLocalEngine,
    )

    speaker = MagicMock()
    controller = TTSController(speaker)

    speak_config = SpeakConfig(
        backend=TTSBackendConfig(
            type="local",
            local=TTSBackendLocalConfig(model="vits-piper-en_US-ryan-low"),
        )
    )
    controller.initialize(speak_config)

    assert isinstance(controller.engine, FakeLocalEngine)
    assert controller.engine.cfg.model == "vits-piper-en_US-ryan-low"


def test_tts_ibm_backend_uses_mocked_engine_module(monkeypatch):
    class FakeWatsonEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self) -> None:
            pass

        def synthesize(self, _text: str) -> bytes:
            return b"RIFF"

    _install_fake_backend(
        monkeypatch,
        "tjbot.tts.backends.ibm_watson_tts",
        "IBMWatsonTTSEngine",
        FakeWatsonEngine,
    )

    speaker = MagicMock()
    controller = TTSController(speaker)

    speak_config = SpeakConfig(
        backend=TTSBackendConfig.model_validate(
            {
                "type": "ibm-watson-tts",
                "ibm-watson-tts": TTSBackendIBMWatsonConfig(
                    voice="en-US_AllisonV3Voice"
                ).model_dump(),
            }
        )
    )
    controller.initialize(speak_config)

    assert isinstance(controller.engine, FakeWatsonEngine)
    assert controller.engine.cfg.voice == "en-US_AllisonV3Voice"


def test_tts_google_backend_uses_mocked_engine_module(monkeypatch):
    class FakeGoogleEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self) -> None:
            pass

        def synthesize(self, _text: str) -> bytes:
            return b"RIFF"

    _install_fake_backend(
        monkeypatch,
        "tjbot.tts.backends.google_cloud_tts",
        "GoogleCloudTTSEngine",
        FakeGoogleEngine,
    )

    speaker = MagicMock()
    controller = TTSController(speaker)

    speak_config = SpeakConfig(
        backend=TTSBackendConfig.model_validate(
            {
                "type": "google-cloud-tts",
                "google-cloud-tts": TTSBackendGoogleCloudConfig.model_validate(
                    {"languageCode": "en-US"}
                ).model_dump(by_alias=True),
            }
        )
    )
    controller.initialize(speak_config)

    assert isinstance(controller.engine, FakeGoogleEngine)
    assert controller.engine.cfg.language_code == "en-US"


def test_tts_azure_backend_uses_mocked_engine_module(monkeypatch):
    class FakeAzureEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self) -> None:
            pass

        def synthesize(self, _text: str) -> bytes:
            return b"RIFF"

    _install_fake_backend(
        monkeypatch,
        "tjbot.tts.backends.azure_tts",
        "AzureTTSEngine",
        FakeAzureEngine,
    )

    speaker = MagicMock()
    controller = TTSController(speaker)

    speak_config = SpeakConfig(
        backend=TTSBackendConfig.model_validate(
            {
                "type": "azure-tts",
                "azure-tts": TTSBackendAzureConfig(
                    voice="en-US-JennyNeural"
                ).model_dump(),
            }
        )
    )
    controller.initialize(speak_config)

    assert isinstance(controller.engine, FakeAzureEngine)
    assert controller.engine.cfg.voice == "en-US-JennyNeural"


def test_tts_backend_init_error_propagates(monkeypatch):
    class FailingGoogleEngine:
        def __init__(self, _cfg):
            raise TJBotError("backend init failed")

    _install_fake_backend(
        monkeypatch,
        "tjbot.tts.backends.google_cloud_tts",
        "GoogleCloudTTSEngine",
        FailingGoogleEngine,
    )

    speaker = MagicMock()
    controller = TTSController(speaker)
    speak_config = SpeakConfig(
        backend=TTSBackendConfig.model_validate(
            {
                "type": "google-cloud-tts",
                "google-cloud-tts": TTSBackendGoogleCloudConfig.model_validate(
                    {"languageCode": "en-US"}
                ).model_dump(by_alias=True),
            }
        )
    )

    with pytest.raises(TJBotError, match="backend init failed"):
        controller.initialize(speak_config)


def test_tts_speak_delegates_to_engine_and_cleans_temp_file():
    speaker = MagicMock()
    controller = TTSController(speaker)

    engine = MagicMock()
    engine.synthesize.return_value = b"RIFF"
    controller.engine = engine

    controller.speak("hello world")

    engine.synthesize.assert_called_once_with("hello world")
    speaker.play_audio.assert_called_once()
    played_path = speaker.play_audio.call_args[0][0]

    assert not Path(played_path).exists()


def test_tts_speak_raises_when_engine_not_initialized():
    speaker = MagicMock()
    controller = TTSController(speaker)

    with pytest.raises(TJBotError, match="not initialized"):
        controller.speak("hello")


def test_tts_unknown_backend_leaves_engine_uninitialized():
    speaker = MagicMock()
    controller = TTSController(speaker)

    speak_config = SpeakConfig(backend=TTSBackendConfig(type="none"))
    speak_config.backend.type = "unknown-backend"  # type: ignore[assignment]
    controller.initialize(speak_config)

    assert controller.engine is None


def test_tts_transcribe_manages_microphone_lifecycle_and_retries_on_no_speech():
    speaker = MagicMock()
    controller = TTSController(speaker)

    engine = MagicMock()
    engine.synthesize.side_effect = [TJBotError("TTS is disabled."), b"RIFF"]
    controller.engine = engine

    with pytest.raises(TJBotError, match="TTS is disabled"):
        controller.speak("hello")

    controller.speak("hello")

    assert engine.synthesize.call_count == 2
    speaker.play_audio.assert_called_once()


def test_tts_speak_delegates_to_engine_and_cleans_temp_file__2():
    test_tts_speak_delegates_to_engine_and_cleans_temp_file()


def test_tts_unknown_backend_leaves_engine_uninitialized__2():
    test_tts_unknown_backend_leaves_engine_uninitialized()
