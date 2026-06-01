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

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from tjbot.config.config_types import (
    ListenConfig,
    STTBackendAzureConfig,
    STTBackendConfig,
    STTBackendGoogleCloudConfig,
    STTBackendIBMWatsonConfig,
    STTBackendLocalConfig,
    VADConfig,
)
from tjbot.stt.stt_utils import infer_local_model_flavor, infer_stt_mode, to_model_type
from tjbot.utils.errors import TJBotError
from tjbot.stt.stt import STTController


def _install_fake_backend(monkeypatch, module_name: str, class_name: str, cls):
    module = types.ModuleType(module_name)
    setattr(module, class_name, cls)
    monkeypatch.setitem(sys.modules, module_name, module)


def test_stt_none_backend_raises_disabled_error():
    config = ListenConfig(backend=STTBackendConfig(type="none"))
    controller = STTController(config)

    with pytest.raises(TJBotError, match="STT is disabled"):
        controller.transcribe(iter([b"audio"]))


def test_stt_unknown_backend_is_not_initialized():
    controller = STTController()
    config = ListenConfig(backend=STTBackendConfig(type="local"))
    config.backend.type = "unknown-backend"  # type: ignore[assignment]

    with pytest.raises(TJBotError, match="Unknown STT backend type"):
        controller.initialize(config)


def test_stt_local_backend_uses_mocked_engine_module(monkeypatch):
    class FakeLocalEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            return "ok"

    _install_fake_backend(
        monkeypatch,
        "tjbot.stt.backends.sherpa_onnx_stt",
        "SherpaONNXSTTEngine",
        FakeLocalEngine,
    )

    config = ListenConfig(
        backend=STTBackendConfig(
            type="local",
            local=STTBackendLocalConfig(model="whisper-tiny"),
        )
    )

    controller = STTController(config)

    assert isinstance(controller.engine, FakeLocalEngine)
    assert controller.engine.cfg.model == "whisper-tiny"


def test_stt_ibm_backend_uses_mocked_engine_module(monkeypatch):
    class FakeWatsonEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            return "ok"

    _install_fake_backend(
        monkeypatch,
        "tjbot.stt.backends.watson_stt",
        "IBMWatsonSTTEngine",
        FakeWatsonEngine,
    )

    config = ListenConfig(
        backend=STTBackendConfig.model_validate(
            {
                "type": "ibm-watson-stt",
                "ibm-watson-stt": STTBackendIBMWatsonConfig(
                    model="en-US_BroadbandModel"
                ).model_dump(),
            }
        )
    )

    controller = STTController(config)

    assert isinstance(controller.engine, FakeWatsonEngine)
    assert controller.engine.cfg.model == "en-US_BroadbandModel"


def test_stt_google_backend_uses_mocked_engine_module(monkeypatch):
    class FakeGoogleEngine:
        def __init__(self, cfg):
            self.cfg = cfg
            self.microphone_rate = 0
            self.microphone_channels = 0

        def initialize(self, microphone_rate, microphone_channels):
            self.microphone_rate = microphone_rate
            self.microphone_channels = microphone_channels

        def transcribe(self, *_args, **_kwargs):
            return "ok"

    _install_fake_backend(
        monkeypatch,
        "tjbot.stt.backends.google_cloud_stt",
        "GoogleCloudSTTEngine",
        FakeGoogleEngine,
    )

    config = ListenConfig(
        microphone_rate=44100,
        microphone_channels=2,
        backend=STTBackendConfig.model_validate(
            {
                "type": "google-cloud-stt",
                "google-cloud-stt": STTBackendGoogleCloudConfig(
                    language_code="en-US"
                ).model_dump(by_alias=True),
            }
        ),
    )

    controller = STTController(config)

    assert isinstance(controller.engine, FakeGoogleEngine)
    assert controller.engine.cfg.language_code == "en-US"
    assert controller.engine.microphone_rate == 44100
    assert controller.engine.microphone_channels == 2


def test_stt_azure_backend_uses_mocked_engine_module(monkeypatch):
    class FakeAzureEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            return "ok"

    _install_fake_backend(
        monkeypatch,
        "tjbot.stt.backends.azure_stt",
        "AzureSTTEngine",
        FakeAzureEngine,
    )

    config = ListenConfig(
        backend=STTBackendConfig.model_validate(
            {
                "type": "azure-stt",
                "azure-stt": STTBackendAzureConfig(language="en-US").model_dump(),
            }
        )
    )

    controller = STTController(config)

    assert isinstance(controller.engine, FakeAzureEngine)
    assert controller.engine.cfg.language == "en-US"


def test_stt_backend_init_error_propagates(monkeypatch):
    class FailingGoogleEngine:
        def __init__(self, _cfg):
            raise TJBotError("backend init failed")

    _install_fake_backend(
        monkeypatch,
        "tjbot.stt.backends.google_cloud_stt",
        "GoogleCloudSTTEngine",
        FailingGoogleEngine,
    )

    config = ListenConfig(
        backend=STTBackendConfig.model_validate(
            {
                "type": "google-cloud-stt",
                "google-cloud-stt": STTBackendGoogleCloudConfig(
                    language_code="en-US"
                ).model_dump(by_alias=True),
            }
        )
    )

    with pytest.raises(TJBotError, match="backend init failed"):
        STTController(config)


def test_watson_transcribe_wraps_audio_in_audiosource_and_parses_final_list(
    monkeypatch,
):
    from tjbot.stt.backends import watson_stt

    captured = {}

    class FakeAudioSource:
        def __init__(self, input_stream, is_recording=False, is_buffer=False):
            self.input = input_stream
            self.is_recording = is_recording
            self.is_buffer = is_buffer

    class FakeWatsonService:
        def recognize_using_websocket(self, **kwargs):
            captured["audio"] = kwargs["audio"]
            assert kwargs["audio"].input.read(4) == b"abcd"
            kwargs["recognize_callback"].on_transcription(
                [{"transcript": "hello world"}]
            )

    monkeypatch.setattr(watson_stt, "AudioSource", FakeAudioSource)

    engine = watson_stt.IBMWatsonSTTEngine(
        STTBackendIBMWatsonConfig(model="en-US_BroadbandModel")
    )
    engine.service = FakeWatsonService()
    engine.microphone_rate = 16000
    engine.microphone_channels = 1

    result = engine.transcribe(iter([b"abcd"]))

    assert isinstance(captured["audio"], FakeAudioSource)
    assert result == "hello world"


def test_watson_transcribe_parses_object_style_results_payload(monkeypatch):
    from tjbot.stt.backends import watson_stt

    class FakeAudioSource:
        def __init__(self, input_stream, is_recording=False, is_buffer=False):
            self.input = input_stream
            self.is_recording = is_recording
            self.is_buffer = is_buffer

    class Alt:
        def __init__(self, transcript):
            self.transcript = transcript

    class Result:
        def __init__(self, transcript, final=True):
            self.alternatives = [Alt(transcript)]
            self.final = final

    class Payload:
        def __init__(self, transcript):
            self.results = [Result(transcript, final=True)]

    class FakeWatsonService:
        def recognize_using_websocket(self, **kwargs):
            kwargs["recognize_callback"].on_transcription(Payload("hello object world"))

    monkeypatch.setattr(watson_stt, "AudioSource", FakeAudioSource)

    engine = watson_stt.IBMWatsonSTTEngine(
        STTBackendIBMWatsonConfig(model="en-US_BroadbandModel")
    )
    engine.service = FakeWatsonService()
    engine.microphone_rate = 16000
    engine.microphone_channels = 1

    result = engine.transcribe(iter([b"abcd"]))

    assert result == "hello object world"


def test_watson_transcribe_consumes_raw_data_results_payload(monkeypatch):
    from tjbot.stt.backends import watson_stt

    class FakeAudioSource:
        def __init__(self, input_stream, is_recording=False, is_buffer=False):
            self.input = input_stream
            self.is_recording = is_recording
            self.is_buffer = is_buffer

    class FakeWatsonService:
        def recognize_using_websocket(self, **kwargs):
            kwargs["recognize_callback"].on_data(
                {
                    "results": [
                        {
                            "final": True,
                            "alternatives": [{"transcript": "hello from data"}],
                        }
                    ]
                }
            )

    monkeypatch.setattr(watson_stt, "AudioSource", FakeAudioSource)

    engine = watson_stt.IBMWatsonSTTEngine(
        STTBackendIBMWatsonConfig(model="en-US_BroadbandModel")
    )
    engine.service = FakeWatsonService()
    engine.microphone_rate = 16000
    engine.microphone_channels = 1

    result = engine.transcribe(iter([b"abcd"]))

    assert result == "hello from data"


def test_google_cloud_transcribe_uses_runtime_resolved_project_id(
    monkeypatch,
):
    from tjbot.stt.backends import google_cloud_stt

    captured = {}

    class FakeSpeechClient:
        def __init__(self, client_options=None):
            captured["endpoint"] = client_options["api_endpoint"]

        def streaming_recognize(self, requests):
            first_request = next(requests)
            captured["recognizer"] = first_request.recognizer
            return [
                types.SimpleNamespace(
                    results=[
                        types.SimpleNamespace(
                            alternatives=[
                                types.SimpleNamespace(transcript="hello world")
                            ],
                            is_final=True,
                        )
                    ]
                )
            ]

    class _Message:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fake_cs = types.SimpleNamespace(
        StreamingRecognitionConfig=_Message,
        RecognitionConfig=_Message,
        RecognitionFeatures=_Message,
        StreamingRecognitionFeatures=_Message,
        StreamingRecognizeRequest=_Message,
        ExplicitDecodingConfig=types.SimpleNamespace(
            AudioEncoding=types.SimpleNamespace(LINEAR16="LINEAR16"),
        ),
    )
    fake_cs.ExplicitDecodingConfig = type(
        "ExplicitDecodingConfig",
        (),
        {
            "AudioEncoding": types.SimpleNamespace(LINEAR16="LINEAR16"),
            "__init__": lambda self, **kwargs: self.__dict__.update(kwargs),
        },
    )

    monkeypatch.setattr(google_cloud_stt, "SpeechClient", FakeSpeechClient)
    monkeypatch.setattr(google_cloud_stt, "cs", fake_cs)
    monkeypatch.setattr(
        google_cloud_stt,
        "load_google_cloud_credentials",
        lambda _path: {"credentialsPath": "/tmp/google-credentials.json"},
    )
    monkeypatch.setattr(
        google_cloud_stt,
        "_resolve_google_project_id",
        lambda: "test-project",
    )

    engine = google_cloud_stt.GoogleCloudSTTEngine(
        STTBackendGoogleCloudConfig(
            model="chirp_3",
            language_code="en-US",
            region="us",
        )
    )
    engine.initialize(16000, 1)

    result = engine.transcribe(iter([b"abcd"]))

    assert captured["endpoint"] == "us-speech.googleapis.com"
    assert captured["recognizer"] == "projects/test-project/locations/us/recognizers/_"
    assert result == "hello world"


def test_azure_transcribe_uses_audio_config_stream_argument(monkeypatch):
    from tjbot.stt.backends import azure_stt

    captured = {}

    class FakeEventSignal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self, evt):
            for callback in list(self._callbacks):
                callback(evt)

    class FakePushAudioInputStream:
        def __init__(self, stream_format=None):
            captured["stream_format"] = stream_format
            self.closed = False

        def write(self, chunk):
            captured.setdefault("chunks", []).append(chunk)

        def close(self):
            self.closed = True

    class FakeAudioConfig:
        def __init__(self, **kwargs):
            captured["audio_config_kwargs"] = kwargs

    class FakeSpeechRecognizer:
        def __init__(self, speech_config=None, audio_config=None):
            _ = speech_config, audio_config
            self.recognized = FakeEventSignal()
            self.recognizing = FakeEventSignal()
            self.canceled = FakeEventSignal()
            self.session_stopped = FakeEventSignal()

        def start_continuous_recognition(self):
            evt = types.SimpleNamespace(
                result=types.SimpleNamespace(
                    reason="RecognizedSpeech",
                    text="hello azure",
                )
            )
            self.recognized.emit(evt)
            self.session_stopped.emit(types.SimpleNamespace())

        def stop_continuous_recognition(self):
            return None

    class FakeSpeechConfig:
        def __init__(self, subscription=None, region=None):
            captured["speech_config"] = {
                "subscription": subscription,
                "region": region,
            }
            self.speech_recognition_language = None

    fake_speechsdk = types.SimpleNamespace(
        SpeechConfig=FakeSpeechConfig,
        SpeechRecognizer=FakeSpeechRecognizer,
        ResultReason=types.SimpleNamespace(
            RecognizedSpeech="RecognizedSpeech",
            RecognizingSpeech="RecognizingSpeech",
        ),
        audio=types.SimpleNamespace(
            AudioStreamFormat=lambda **kwargs: types.SimpleNamespace(**kwargs),
            PushAudioInputStream=FakePushAudioInputStream,
            AudioConfig=FakeAudioConfig,
        ),
    )

    monkeypatch.setattr(azure_stt, "speechsdk", fake_speechsdk)
    monkeypatch.setattr(
        azure_stt,
        "load_azure_credentials",
        lambda _path: {"speechKey": "key", "speechRegion": "eastus"},
    )

    engine = azure_stt.AzureSTTEngine(STTBackendAzureConfig(language="en-US"))
    engine.initialize(16000, 1)

    result = engine.transcribe(iter([b"abcd"]))

    assert captured["audio_config_kwargs"] == {
        "stream": captured["audio_config_kwargs"]["stream"]
    }
    assert captured["chunks"] == [b"abcd"]
    assert result == "hello azure"


def test_stt_transcribe_delegates_to_engine():
    config = ListenConfig(backend=STTBackendConfig(type="none"))
    controller = STTController(config)

    partial_cb = MagicMock()
    final_cb = MagicMock()

    fake_engine = MagicMock()
    fake_engine.transcribe.return_value = "hello world"
    controller.engine = fake_engine

    stream = iter([b"a", b"b"])
    result = controller.transcribe(
        stream, on_partial_result=partial_cb, on_final_result=final_cb
    )

    assert result == "hello world"
    fake_engine.transcribe.assert_called_once_with(
        stream,
        {
            "on_partial_result": partial_cb,
            "on_final_result": final_cb,
            "abort_signal": None,
        },
    )


def test_stt_transcribe_forwards_abort_signal_to_engine():
    config = ListenConfig(backend=STTBackendConfig(type="none"))
    controller = STTController(config)

    fake_engine = MagicMock()
    fake_engine.transcribe.return_value = ""
    controller.engine = fake_engine

    stream = iter([b"audio"])
    abort_signal = MagicMock()

    controller.transcribe(stream, abort_signal=abort_signal)

    fake_engine.transcribe.assert_called_once_with(
        stream,
        {
            "on_partial_result": None,
            "on_final_result": None,
            "abort_signal": abort_signal,
        },
    )


def test_stt_transcribe_manages_microphone_lifecycle_and_retries_on_no_speech():
    class FakeMicrophoneController:
        def __init__(self):
            self.start_calls = 0
            self.pause_calls = 0
            self.stream = iter([b"audio"])

        def start(self):
            self.start_calls += 1

        def pause(self):
            self.pause_calls += 1

        def get_input_stream(self):
            return self.stream

    mic = FakeMicrophoneController()
    controller = STTController(microphone_controller=mic)
    controller.config = ListenConfig(backend=STTBackendConfig(type="none"))

    fake_engine = MagicMock()
    fake_engine.transcribe.side_effect = [
        TJBotError("no speech", code="stt.no-speech"),
        "hello world",
    ]
    controller.engine = fake_engine

    result = controller.transcribe()

    assert result == "hello world"
    assert mic.start_calls == 2
    assert mic.pause_calls == 2


"""
Tests for stt_utils.py - infer_stt_mode and infer_local_model_flavor
"""


class TestInferLocalModelFlavor:
    def test_whisper(self):
        assert infer_local_model_flavor("whisper-tiny") == "offline-whisper"

    def test_moonshine(self):
        assert infer_local_model_flavor("moonshine-base") == "offline-moonshine"

    def test_zipformer(self):
        assert (
            infer_local_model_flavor("streaming-zipformer-en") == "streaming-zipformer"
        )

    def test_transducer(self):
        assert infer_local_model_flavor("transducer-model") == "streaming-zipformer"

    def test_paraformer(self):
        assert (
            infer_local_model_flavor("paraformer-en-streaming")
            == "streaming-paraformer"
        )

    def test_url_fallback(self):
        assert (
            infer_local_model_flavor(
                None, "https://huggingface.co/models/whisper-large"
            )
            == "offline-whisper"
        )

    def test_unknown_raises(self):
        with pytest.raises(TJBotError, match="Unable to infer STT model type"):
            infer_local_model_flavor("unknown-model")


class TestToModelType:
    def test_streaming_flavors(self):
        assert to_model_type("streaming-zipformer") == "streaming"
        assert to_model_type("streaming-paraformer") == "streaming"

    def test_offline_flavors(self):
        assert to_model_type("offline-whisper") == "offline"
        assert to_model_type("offline-moonshine") == "offline"


class TestInferSTTMode:
    def _config(self, backend_type, **kwargs):
        backend = STTBackendConfig(type=backend_type)
        return ListenConfig(backend=backend)

    def test_ibm_watson_no_interim(self):
        cfg = ListenConfig(
            backend=STTBackendConfig(
                type="ibm-watson-stt",
                **{"ibm-watson-stt": STTBackendIBMWatsonConfig(interim_results=False)},
            )
        )
        assert infer_stt_mode(cfg) == "offline"

    def test_ibm_watson_interim(self):
        cfg = ListenConfig(
            backend=STTBackendConfig(
                type="ibm-watson-stt",
                **{"ibm-watson-stt": STTBackendIBMWatsonConfig(interim_results=True)},
            )
        )
        assert infer_stt_mode(cfg) == "streaming"

    def test_google_cloud_no_interim(self):
        cfg = ListenConfig(
            backend=STTBackendConfig(
                type="google-cloud-stt",
                **{
                    "google-cloud-stt": STTBackendGoogleCloudConfig(
                        interim_results=False
                    )
                },
            )
        )
        assert infer_stt_mode(cfg) == "offline"

    def test_google_cloud_interim(self):
        cfg = ListenConfig(
            backend=STTBackendConfig(
                type="google-cloud-stt",
                **{
                    "google-cloud-stt": STTBackendGoogleCloudConfig(
                        interim_results=True
                    )
                },
            )
        )
        assert infer_stt_mode(cfg) == "streaming"

    def test_azure_always_offline(self):
        cfg = ListenConfig(backend=STTBackendConfig(type="azure-stt"))
        assert infer_stt_mode(cfg) == "offline"

    def test_none_backend_offline(self):
        cfg = ListenConfig(backend=STTBackendConfig(type="none"))
        assert infer_stt_mode(cfg) == "offline"

    def test_local_whisper_offline(self):
        cfg = ListenConfig(
            backend=STTBackendConfig(
                type="local", local=STTBackendLocalConfig(model="whisper-tiny")
            )
        )
        assert infer_stt_mode(cfg) == "offline"

    def test_local_zipformer_streaming(self):
        cfg = ListenConfig(
            backend=STTBackendConfig(
                type="local",
                local=STTBackendLocalConfig(model="streaming-zipformer-en"),
            )
        )
        assert infer_stt_mode(cfg) == "streaming"

    def test_unknown_backend_raises(self):
        backend = STTBackendConfig.model_construct(type="unknown-backend")
        cfg = ListenConfig.model_construct(backend=backend)
        with pytest.raises(TJBotError, match="Unknown STT backend type"):
            infer_stt_mode(cfg)


"""
Unit tests for the SherpaONNX STT backend, focusing on VAD routing,
energy-based fallback, and _should_use_vad() logic.
All tests mock the sherpa_onnx module and the model registry.
"""


# ---------------------------------------------------------------------------
# Helpers to build fake sherpa_onnx and registry
# ---------------------------------------------------------------------------


def _make_fake_sherpa():
    """Return a fake sherpa_onnx module."""
    fake = types.ModuleType("sherpa_onnx")

    class FakeStream:
        def __init__(self):
            self.result = types.SimpleNamespace(text="hello world")

        def accept_waveform(self, *_args, **_kwargs):
            pass

        def input_finished(self):
            pass

    class FakeOfflineRecognizer:
        @staticmethod
        def from_moonshine(**_kwargs):
            return FakeOfflineRecognizer()

        @staticmethod
        def from_whisper(**_kwargs):
            return FakeOfflineRecognizer()

        def create_stream(self):
            return FakeStream()

        def decode_stream(self, _stream):
            pass

    fake.OfflineRecognizer = FakeOfflineRecognizer

    class FakeOnlineRecognizer:
        @staticmethod
        def from_transducer(**_kwargs):
            return FakeOnlineRecognizer()

        @staticmethod
        def from_paraformer(**_kwargs):
            return FakeOnlineRecognizer()

        def create_stream(self):
            return FakeStream()

        def is_ready(self, _s):
            return False

        def decode_stream(self, _s):
            pass

        def get_result(self, _s):
            return types.SimpleNamespace(text="")

        def is_endpoint(self, _s):
            return False

        def reset(self, _s):
            pass

    fake.OnlineRecognizer = FakeOnlineRecognizer

    class FakeVadSegment:
        def __init__(self, samples):
            self.samples = samples

    class FakeVAD:
        def __init__(self, _config, buffer_size_in_seconds=60):
            self._segments = []

        def accept_waveform(self, _samples):
            pass

        def is_empty(self):
            return len(self._segments) == 0

        def front(self):
            return self._segments[0]

        def pop(self):
            self._segments.pop(0)

    fake.VoiceActivityDetector = FakeVAD
    fake.VadModelConfig = MagicMock(return_value=object())
    fake.SileroVadModelConfig = MagicMock(return_value=object())

    return fake, FakeVAD, FakeVadSegment


def _install_fake_sherpa(monkeypatch):
    fake_sherpa, FakeVAD, FakeVadSegment = _make_fake_sherpa()
    # Set __spec__ to avoid errors in importlib.util.find_spec
    fake_sherpa.__spec__ = types.SimpleNamespace(submodule_search_locations=[])
    monkeypatch.setitem(sys.modules, "sherpa_onnx", fake_sherpa)
    return fake_sherpa, FakeVAD, FakeVadSegment


def _make_registry(monkeypatch, tmp_path: Path, vad_path: str = "silero_vad.onnx"):
    """Patch the ModelRegistry used by SherpaONNXSTTEngine."""
    from tjbot.utils.model_registry import ModelMetadata

    stt_info = ModelMetadata(
        type="stt",
        key="moonshine-tiny",
        label="Moonshine Tiny",
        url="https://example.com/moonshine.zip",
        folder="moonshine_tiny",
        required=[
            "preprocess.onnx",
            "encode.int8.onnx",
            "uncached_decode.int8.onnx",
            "cached_decode.int8.onnx",
            "tokens.txt",
        ],
        kind="offline-moonshine",
    )
    vad_info = ModelMetadata(
        type="vad",
        key="silero-vad",
        label="Silero VAD",
        url="https://example.com/silero_vad.onnx",
        folder="silero_vad",
        required=[vad_path],
        kind=None,
    )

    # Create dummy model files so path-existence checks pass
    model_dir = tmp_path / "stt" / "moonshine_tiny"
    model_dir.mkdir(parents=True)
    for fname in stt_info.required:
        (model_dir / fname).touch()

    vad_dir = tmp_path / "vad" / "silero_vad"
    vad_dir.mkdir(parents=True)
    (vad_dir / vad_path).touch()

    registry = MagicMock()
    registry.load_model.side_effect = (
        lambda key: stt_info if "moonshine" in key else vad_info
    )
    registry.get_model_cache_dir_for_type.side_effect = lambda t: tmp_path / t
    registry.is_model_downloaded.return_value = True

    monkeypatch.setattr(
        "tjbot.utils.model_registry.ModelRegistry",
        types.SimpleNamespace(get_instance=lambda: registry),
    )
    return registry


def _make_engine(monkeypatch, tmp_path, vad_config=None):
    _install_fake_sherpa(monkeypatch)
    _make_registry(monkeypatch, tmp_path)

    from tjbot.stt.backends.sherpa_onnx_stt import SherpaONNXSTTEngine

    config = STTBackendLocalConfig(model="moonshine-tiny", vad=vad_config)
    engine = SherpaONNXSTTEngine(config)
    engine.initialize(16000, 1)
    return engine


# ---------------------------------------------------------------------------
# Tests: _should_use_vad()
# ---------------------------------------------------------------------------


class TestShouldUseVad:
    def test_false_when_no_vad_path(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path, vad_config=None)
        assert engine._should_use_vad() is False

    def test_false_when_vad_disabled_in_config(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch,
            tmp_path,
            vad_config=VADConfig(enabled=False, model="silero-vad"),
        )
        engine._vad_path = "/tmp/silero_vad.onnx"
        assert engine._should_use_vad() is False

    def test_true_when_vad_path_set_and_enabled(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch,
            tmp_path,
            vad_config=VADConfig(enabled=True, model="silero-vad"),
        )
        engine._vad_path = "/tmp/silero_vad.onnx"
        assert engine._should_use_vad() is True

    def test_false_for_streaming_model(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch,
            tmp_path,
            vad_config=VADConfig(enabled=True, model="silero-vad"),
        )
        engine._vad_path = "/tmp/silero_vad.onnx"
        engine._model_kind = "streaming-zipformer"
        assert engine._should_use_vad() is False


# ---------------------------------------------------------------------------
# Tests: VAD loading during _initialize()
# ---------------------------------------------------------------------------


class TestVADLoading:
    def test_vad_path_set_when_config_provided(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch,
            tmp_path,
            vad_config=VADConfig(enabled=True, model="silero-vad"),
        )
        assert engine._vad_path is not None
        assert "silero_vad.onnx" in engine._vad_path

    def test_vad_path_not_set_without_config(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path, vad_config=None)
        assert engine._vad_path is None

    def test_vad_path_not_set_when_disabled(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch,
            tmp_path,
            vad_config=VADConfig(enabled=False, model="silero-vad"),
        )
        assert engine._vad_path is None


# ---------------------------------------------------------------------------
# Tests: transcribe() routing
# ---------------------------------------------------------------------------


class TestTranscribeRouting:
    def test_routes_to_energy_when_no_vad(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path, vad_config=None)

        called = []
        engine._transcribe_offline_energy = (
            lambda *a, **kw: called.append("energy") or "hi"
        )

        # Offline model, no VAD
        engine._model_kind = "offline-whisper"
        result = engine.transcribe(iter([]))
        assert called == ["energy"]
        assert result == "hi"

    def test_routes_to_vad_when_vad_path_set(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch,
            tmp_path,
            vad_config=VADConfig(enabled=True, model="silero-vad"),
        )

        called = []
        engine._transcribe_offline_with_vad = (
            lambda *a, **kw: called.append("vad") or "hello"
        )

        engine._model_kind = "offline-moonshine"
        result = engine.transcribe(iter([]))
        assert called == ["vad"]
        assert result == "hello"

    def test_routes_to_online_for_zipformer(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path)

        called = []
        engine._transcribe_online = lambda *a, **kw: called.append("online") or "zip"

        engine._model_kind = "streaming-zipformer"
        result = engine.transcribe(iter([]))
        assert called == ["online"]
        assert result == "zip"


# ---------------------------------------------------------------------------
# Tests: _transcribe_offline_energy()
# ---------------------------------------------------------------------------


class TestTranscribeOfflineEnergy:
    def _make_chunk(self, amplitude: float, num_samples: int = 1600) -> bytes:
        """Return int16 PCM bytes with uniform amplitude."""
        samples = np.full(num_samples, int(amplitude * 32767), dtype=np.int16)
        return samples.tobytes()

    def test_returns_empty_string_for_silent_audio(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path)
        silent_chunks = [self._make_chunk(0.0) for _ in range(5)]
        result = engine._transcribe_offline_energy(iter(silent_chunks), None, None)
        assert result == ""

    def test_decodes_speech_after_silence_threshold(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path)

        # Provide loud chunk then several silent chunks to trigger decode
        speech_chunk = self._make_chunk(0.5, num_samples=3200)  # loud
        silence_chunk = self._make_chunk(0.0, num_samples=3200)  # 200ms each at 16kHz

        # 4 silence chunks × 200ms = 800ms > 700ms threshold
        chunks = [speech_chunk] + [silence_chunk] * 4
        final_texts = []
        result = engine._transcribe_offline_energy(
            iter(chunks), None, lambda t: final_texts.append(t)
        )
        assert result == "hello world"
        assert final_texts == ["hello world"]

    def test_partial_callback_called_on_decode(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path)

        speech_chunk = self._make_chunk(0.5, num_samples=3200)
        silence_chunk = self._make_chunk(0.0, num_samples=3200)
        chunks = [speech_chunk] + [silence_chunk] * 4

        partials = []
        engine._transcribe_offline_energy(
            iter(chunks), lambda t: partials.append(t), None
        )
        assert "hello world" in partials


# ---------------------------------------------------------------------------
# Tests: _transcribe_offline_with_vad()
# ---------------------------------------------------------------------------


class TestTranscribeOfflineWithVad:
    def test_handles_vad_front_property_and_pop_method(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch,
            tmp_path,
            vad_config=VADConfig(enabled=True, model="silero-vad"),
        )
        engine._vad_path = "/tmp/silero_vad.onnx"

        samples = np.zeros(512, dtype=np.float32)
        segment = types.SimpleNamespace(samples=samples)

        class PropertyFrontVAD:
            def __init__(self):
                self._done = False
                self.front = segment

            def accept_waveform(self, _s):
                pass

            def empty(self):
                return self._done

            def pop(self):
                self._done = True

        engine._create_silero_vad = lambda _path: PropertyFrontVAD()

        result = engine._transcribe_offline_with_vad(iter([b"\x00" * 1024]), None, None)
        assert result == "hello world"

    def test_returns_empty_when_no_segments(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch,
            tmp_path,
            vad_config=VADConfig(enabled=True, model="silero-vad"),
        )
        engine._vad_path = "/tmp/silero_vad.onnx"

        # Override _create_silero_vad to return a VAD with no segments
        empty_vad = MagicMock()
        empty_vad.is_empty.return_value = True
        engine._create_silero_vad = lambda _path: empty_vad

        result = engine._transcribe_offline_with_vad(iter([b"\x00" * 100]), None, None)
        assert result == ""

    def test_decodes_segment_when_vad_fires(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch,
            tmp_path,
            vad_config=VADConfig(enabled=True, model="silero-vad"),
        )
        engine._vad_path = "/tmp/silero_vad.onnx"

        samples = np.zeros(512, dtype=np.float32)
        segment = types.SimpleNamespace(samples=samples)

        call_count = [0]

        class SingleSegmentVAD:
            def accept_waveform(self, _s):
                pass

            def is_empty(self_):
                return call_count[0] >= 1

            def front(self_):
                return segment

            def pop(self_):
                call_count[0] += 1

        engine._create_silero_vad = lambda _path: SingleSegmentVAD()

        finals = []
        result = engine._transcribe_offline_with_vad(
            iter([b"\x00" * 1024]), None, lambda t: finals.append(t)
        )
        assert result == "hello world"
        assert finals == ["hello world"]
