import sys
import types
from unittest.mock import MagicMock

import pytest

from tjbot.config.config_types import (
    ListenConfig,
    STTBackendAzureConfig,
    STTBackendConfig,
    STTBackendGoogleCloudConfig,
    STTBackendIBMWatsonConfig,
    STTBackendLocalConfig,
)
from tjbot.utils.errors import TJBotError
from tjbot.stt.stt import STTController


def _install_fake_backend(monkeypatch, module_name: str, class_name: str, cls):
    module = types.ModuleType(module_name)
    setattr(module, class_name, cls)
    monkeypatch.setitem(sys.modules, module_name, module)


def test_stt_none_backend_raises_disabled_error():
    config = ListenConfig(backend=STTBackendConfig(type='none'))
    controller = STTController(config)

    with pytest.raises(TJBotError, match='STT is disabled'):
        controller.transcribe(iter([b'audio']))


def test_stt_unknown_backend_is_not_initialized():
    controller = STTController()
    config = ListenConfig(backend=STTBackendConfig(type='local'))
    config.backend.type = 'unknown-backend'  # type: ignore[assignment]

    with pytest.raises(TJBotError, match='Unknown STT backend type'):
        controller.initialize(config)


def test_stt_local_backend_uses_mocked_engine_module(monkeypatch):
    class FakeLocalEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            return 'ok'

    _install_fake_backend(
        monkeypatch,
        'tjbot.stt.backends.sherpa_onnx_stt',
        'SherpaONNXSTTEngine',
        FakeLocalEngine,
    )

    config = ListenConfig(
        backend=STTBackendConfig(
            type='local',
            local=STTBackendLocalConfig(model='whisper-tiny'),
        )
    )

    controller = STTController(config)

    assert isinstance(controller.engine, FakeLocalEngine)
    assert controller.engine.cfg.model == 'whisper-tiny'


def test_stt_ibm_backend_uses_mocked_engine_module(monkeypatch):
    class FakeWatsonEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            return 'ok'

    _install_fake_backend(
        monkeypatch,
        'tjbot.stt.backends.watson_stt',
        'IBMWatsonSTTEngine',
        FakeWatsonEngine,
    )

    config = ListenConfig(
        backend=STTBackendConfig.model_validate(
            {
                'type': 'ibm-watson-stt',
                'ibm-watson-stt': STTBackendIBMWatsonConfig(model='en-US_BroadbandModel').model_dump(),
            }
        )
    )

    controller = STTController(config)

    assert isinstance(controller.engine, FakeWatsonEngine)
    assert controller.engine.cfg.model == 'en-US_BroadbandModel'


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
            return 'ok'

    _install_fake_backend(
        monkeypatch,
        'tjbot.stt.backends.google_cloud_stt',
        'GoogleCloudSTTEngine',
        FakeGoogleEngine,
    )

    config = ListenConfig(
        microphone_rate=44100,
        microphone_channels=2,
        backend=STTBackendConfig.model_validate(
            {
                'type': 'google-cloud-stt',
                'google-cloud-stt': STTBackendGoogleCloudConfig(language_code='en-US').model_dump(by_alias=True),
            }
        ),
    )

    controller = STTController(config)

    assert isinstance(controller.engine, FakeGoogleEngine)
    assert controller.engine.cfg.language_code == 'en-US'
    assert controller.engine.microphone_rate == 44100
    assert controller.engine.microphone_channels == 2


def test_stt_azure_backend_uses_mocked_engine_module(monkeypatch):
    class FakeAzureEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def initialize(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            return 'ok'

    _install_fake_backend(
        monkeypatch,
        'tjbot.stt.backends.azure_stt',
        'AzureSTTEngine',
        FakeAzureEngine,
    )

    config = ListenConfig(
        backend=STTBackendConfig.model_validate(
            {
                'type': 'azure-stt',
                'azure-stt': STTBackendAzureConfig(language='en-US').model_dump(),
            }
        )
    )

    controller = STTController(config)

    assert isinstance(controller.engine, FakeAzureEngine)
    assert controller.engine.cfg.language == 'en-US'


def test_stt_backend_init_error_propagates(monkeypatch):
    class FailingGoogleEngine:
        def __init__(self, _cfg):
            raise TJBotError('backend init failed')

    _install_fake_backend(
        monkeypatch,
        'tjbot.stt.backends.google_cloud_stt',
        'GoogleCloudSTTEngine',
        FailingGoogleEngine,
    )

    config = ListenConfig(
        backend=STTBackendConfig.model_validate(
            {
                'type': 'google-cloud-stt',
                'google-cloud-stt': STTBackendGoogleCloudConfig(language_code='en-US').model_dump(by_alias=True),
            }
        )
    )

    with pytest.raises(TJBotError, match='backend init failed'):
        STTController(config)


def test_stt_transcribe_delegates_to_engine():
    config = ListenConfig(backend=STTBackendConfig(type='none'))
    controller = STTController(config)

    partial_cb = MagicMock()
    final_cb = MagicMock()

    fake_engine = MagicMock()
    fake_engine.transcribe.return_value = 'hello world'
    controller.engine = fake_engine

    stream = iter([b'a', b'b'])
    result = controller.transcribe(stream, on_partial_result=partial_cb, on_final_result=final_cb)

    assert result == 'hello world'
    fake_engine.transcribe.assert_called_once_with(
        stream,
        {
            'on_partial_result': partial_cb,
            'on_final_result': final_cb,
            'abort_signal': None,
        },
    )


def test_stt_transcribe_manages_microphone_lifecycle_and_retries_on_no_speech():
    class FakeMicrophoneController:
        def __init__(self):
            self.start_calls = 0
            self.pause_calls = 0
            self.stream = iter([b'audio'])

        def start(self):
            self.start_calls += 1

        def pause(self):
            self.pause_calls += 1

        def get_input_stream(self):
            return self.stream

    mic = FakeMicrophoneController()
    controller = STTController(microphone_controller=mic)
    controller.config = ListenConfig(backend=STTBackendConfig(type='none'))

    fake_engine = MagicMock()
    fake_engine.transcribe.side_effect = [
        TJBotError('no speech', code='stt.no-speech'),
        'hello world',
    ]
    controller.engine = fake_engine

    result = controller.transcribe()

    assert result == 'hello world'
    assert mic.start_calls == 2
    assert mic.pause_calls == 2
