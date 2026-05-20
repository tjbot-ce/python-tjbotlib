"""
Unit tests for the SherpaONNX STT backend, focusing on VAD routing,
energy-based fallback, and _should_use_vad() logic.
All tests mock the sherpa_onnx module and the model registry.
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import numpy as np
import pytest

from tjbot.config.config_types import STTBackendLocalConfig, VADConfig
from tjbot.utils.errors import TJBotError


# ---------------------------------------------------------------------------
# Helpers to build fake sherpa_onnx and registry
# ---------------------------------------------------------------------------

def _make_fake_sherpa():
    """Return a fake sherpa_onnx module."""
    fake = types.ModuleType('sherpa_onnx')

    class FakeStream:
        def __init__(self):
            self.result = types.SimpleNamespace(text='hello world')
        def accept_waveform(self, *_args, **_kwargs): pass
        def input_finished(self): pass

    class FakeOfflineRecognizer:
        @staticmethod
        def from_moonshine(**_kwargs): return FakeOfflineRecognizer()
        @staticmethod
        def from_whisper(**_kwargs): return FakeOfflineRecognizer()
        def create_stream(self): return FakeStream()
        def decode_stream(self, _stream): pass

    fake.OfflineRecognizer = FakeOfflineRecognizer

    class FakeOnlineRecognizer:
        @staticmethod
        def from_transducer(**_kwargs): return FakeOnlineRecognizer()
        @staticmethod
        def from_paraformer(**_kwargs): return FakeOnlineRecognizer()
        def create_stream(self): return FakeStream()
        def is_ready(self, _s): return False
        def decode_stream(self, _s): pass
        def get_result(self, _s): return types.SimpleNamespace(text='')
        def is_endpoint(self, _s): return False
        def reset(self, _s): pass

    fake.OnlineRecognizer = FakeOnlineRecognizer

    class FakeVadSegment:
        def __init__(self, samples):
            self.samples = samples

    class FakeVAD:
        def __init__(self, _config, buffer_size_in_seconds=60):
            self._segments = []
        def accept_waveform(self, _samples): pass
        def is_empty(self): return len(self._segments) == 0
        def front(self): return self._segments[0]
        def pop(self): self._segments.pop(0)

    fake.VoiceActivityDetector = FakeVAD
    fake.VadModelConfig = MagicMock(return_value=object())
    fake.SileroVadModelConfig = MagicMock(return_value=object())

    return fake, FakeVAD, FakeVadSegment


def _install_fake_sherpa(monkeypatch):
    fake_sherpa, FakeVAD, FakeVadSegment = _make_fake_sherpa()
    monkeypatch.setitem(sys.modules, 'sherpa_onnx', fake_sherpa)
    return fake_sherpa, FakeVAD, FakeVadSegment


def _make_registry(monkeypatch, tmp_path: Path, vad_path: str = 'silero_vad.onnx'):
    """Patch the ModelRegistry used by SherpaONNXSTTEngine."""
    from tjbot.utils.model_registry import ModelMetadata

    stt_info = ModelMetadata(
        type='stt',
        key='moonshine-tiny',
        label='Moonshine Tiny',
        url='https://example.com/moonshine.zip',
        folder='moonshine_tiny',
        required=['preprocess.onnx', 'encode.int8.onnx',
                  'uncached_decode.int8.onnx', 'cached_decode.int8.onnx', 'tokens.txt'],
        kind='offline-moonshine',
    )
    vad_info = ModelMetadata(
        type='vad',
        key='silero-vad',
        label='Silero VAD',
        url='https://example.com/silero_vad.onnx',
        folder='silero_vad',
        required=[vad_path],
        kind=None,
    )

    # Create dummy model files so path-existence checks pass
    model_dir = tmp_path / 'stt' / 'moonshine_tiny'
    model_dir.mkdir(parents=True)
    for fname in stt_info.required:
        (model_dir / fname).touch()

    vad_dir = tmp_path / 'vad' / 'silero_vad'
    vad_dir.mkdir(parents=True)
    (vad_dir / vad_path).touch()

    registry = MagicMock()
    registry.load_model.side_effect = lambda key: stt_info if 'moonshine' in key else vad_info
    registry.get_model_cache_dir_for_type.side_effect = lambda t: tmp_path / t
    registry.is_model_downloaded.return_value = True

    monkeypatch.setattr(
        'tjbot.utils.model_registry.ModelRegistry',
        types.SimpleNamespace(get_instance=lambda: registry),
    )
    return registry


def _make_engine(monkeypatch, tmp_path, vad_config=None):
    _install_fake_sherpa(monkeypatch)
    _make_registry(monkeypatch, tmp_path)

    from tjbot.stt.backends.sherpa_onnx_stt import SherpaONNXSTTEngine
    config = STTBackendLocalConfig(model='moonshine-tiny', vad=vad_config)
    return SherpaONNXSTTEngine(config)


# ---------------------------------------------------------------------------
# Tests: _should_use_vad()
# ---------------------------------------------------------------------------

class TestShouldUseVad:
    def test_false_when_no_vad_path(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path, vad_config=None)
        assert engine._should_use_vad() is False

    def test_false_when_vad_disabled_in_config(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path,
                               vad_config=VADConfig(enabled=False, model='silero-vad'))
        engine._vad_path = '/tmp/silero_vad.onnx'
        assert engine._should_use_vad() is False

    def test_true_when_vad_path_set_and_enabled(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path,
                               vad_config=VADConfig(enabled=True, model='silero-vad'))
        engine._vad_path = '/tmp/silero_vad.onnx'
        assert engine._should_use_vad() is True

    def test_false_for_streaming_model(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path,
                               vad_config=VADConfig(enabled=True, model='silero-vad'))
        engine._vad_path = '/tmp/silero_vad.onnx'
        engine._model_kind = 'streaming-zipformer'
        assert engine._should_use_vad() is False


# ---------------------------------------------------------------------------
# Tests: VAD loading during _initialize()
# ---------------------------------------------------------------------------

class TestVADLoading:
    def test_vad_path_set_when_config_provided(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch, tmp_path,
            vad_config=VADConfig(enabled=True, model='silero-vad'),
        )
        assert engine._vad_path is not None
        assert 'silero_vad.onnx' in engine._vad_path

    def test_vad_path_not_set_without_config(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path, vad_config=None)
        assert engine._vad_path is None

    def test_vad_path_not_set_when_disabled(self, monkeypatch, tmp_path):
        engine = _make_engine(
            monkeypatch, tmp_path,
            vad_config=VADConfig(enabled=False, model='silero-vad'),
        )
        assert engine._vad_path is None


# ---------------------------------------------------------------------------
# Tests: transcribe() routing
# ---------------------------------------------------------------------------

class TestTranscribeRouting:
    def test_routes_to_energy_when_no_vad(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path, vad_config=None)

        called = []
        engine._transcribe_offline_energy = lambda *a, **kw: called.append('energy') or 'hi'

        # Offline model, no VAD
        engine._model_kind = 'offline-whisper'
        result = engine.transcribe(iter([]))
        assert called == ['energy']
        assert result == 'hi'

    def test_routes_to_vad_when_vad_path_set(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path,
                               vad_config=VADConfig(enabled=True, model='silero-vad'))

        called = []
        engine._transcribe_offline_with_vad = lambda *a, **kw: called.append('vad') or 'hello'

        engine._model_kind = 'offline-moonshine'
        result = engine.transcribe(iter([]))
        assert called == ['vad']
        assert result == 'hello'

    def test_routes_to_online_for_zipformer(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path)

        called = []
        engine._transcribe_online = lambda *a, **kw: called.append('online') or 'zip'

        engine._model_kind = 'streaming-zipformer'
        result = engine.transcribe(iter([]))
        assert called == ['online']
        assert result == 'zip'


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
        assert result == ''

    def test_decodes_speech_after_silence_threshold(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path)

        # Provide loud chunk then several silent chunks to trigger decode
        speech_chunk = self._make_chunk(0.5, num_samples=3200)    # loud
        silence_chunk = self._make_chunk(0.0, num_samples=3200)   # 200ms each at 16kHz

        # 4 silence chunks × 200ms = 800ms > 700ms threshold
        chunks = [speech_chunk] + [silence_chunk] * 4
        final_texts = []
        result = engine._transcribe_offline_energy(
            iter(chunks), None, lambda t: final_texts.append(t)
        )
        assert result == 'hello world'
        assert final_texts == ['hello world']

    def test_partial_callback_called_on_decode(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path)

        speech_chunk = self._make_chunk(0.5, num_samples=3200)
        silence_chunk = self._make_chunk(0.0, num_samples=3200)
        chunks = [speech_chunk] + [silence_chunk] * 4

        partials = []
        engine._transcribe_offline_energy(iter(chunks), lambda t: partials.append(t), None)
        assert 'hello world' in partials


# ---------------------------------------------------------------------------
# Tests: _transcribe_offline_with_vad()
# ---------------------------------------------------------------------------

class TestTranscribeOfflineWithVad:
    def test_returns_empty_when_no_segments(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path,
                               vad_config=VADConfig(enabled=True, model='silero-vad'))
        engine._vad_path = '/tmp/silero_vad.onnx'

        # Override _create_silero_vad to return a VAD with no segments
        empty_vad = MagicMock()
        empty_vad.is_empty.return_value = True
        engine._create_silero_vad = lambda _path: empty_vad

        result = engine._transcribe_offline_with_vad(iter([b'\x00' * 100]), None, None)
        assert result == ''

    def test_decodes_segment_when_vad_fires(self, monkeypatch, tmp_path):
        engine = _make_engine(monkeypatch, tmp_path,
                               vad_config=VADConfig(enabled=True, model='silero-vad'))
        engine._vad_path = '/tmp/silero_vad.onnx'

        samples = np.zeros(512, dtype=np.float32)
        segment = types.SimpleNamespace(samples=samples)

        call_count = [0]

        class SingleSegmentVAD:
            def accept_waveform(self, _s): pass
            def is_empty(self_):
                return call_count[0] >= 1
            def front(self_):
                return segment
            def pop(self_):
                call_count[0] += 1

        engine._create_silero_vad = lambda _path: SingleSegmentVAD()

        finals = []
        result = engine._transcribe_offline_with_vad(
            iter([b'\x00' * 1024]), None, lambda t: finals.append(t)
        )
        assert result == 'hello world'
        assert finals == ['hello world']
