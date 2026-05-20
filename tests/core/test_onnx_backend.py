import asyncio
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tjbot.config.config_types import SeeBackendLocalConfig
from tjbot.utils.errors import TJBotError
from tjbot.utils.model_registry import ModelMetadata
from tjbot.vision.backends import onnx as onnx_backend
from tjbot.vision.backends.onnx import LoadedModel, ONNXVisionEngine


class _FakeIO:
    def __init__(self, name: str):
        self.name = name


class _FakeSession:
    def __init__(self, outputs, output_names):
        self._outputs = outputs
        self._output_names = output_names

    def get_inputs(self):
        return [_FakeIO('input_0')]

    def get_outputs(self):
        return [_FakeIO(name) for name in self._output_names]

    def run(self, _, feeds):
        assert 'input_0' in feeds
        return self._outputs


def _make_config() -> SeeBackendLocalConfig:
    return SeeBackendLocalConfig(
        object_detection_model='ssd-mobilenet-v2',
        image_classification_model='mobilenetv3',
        face_detection_model='scrfd-2.5g',
        object_detection_confidence=0.5,
        image_classification_confidence=0.4,
        face_detection_confidence=0.3,
    )


def test_onnx_requires_optional_dependencies(monkeypatch):
    engine = ONNXVisionEngine(_make_config())

    monkeypatch.setattr(onnx_backend, 'ort', None)
    monkeypatch.setattr(onnx_backend, 'np', None)
    monkeypatch.setattr(onnx_backend, 'Image', None)

    with pytest.raises(TJBotError, match='requires onnxruntime, numpy, and Pillow'):
        asyncio.run(engine.initialize())


def test_onnx_initialize_loads_three_configured_models(monkeypatch):
    engine = ONNXVisionEngine(_make_config())

    monkeypatch.setattr(onnx_backend, 'ort', object())
    monkeypatch.setattr(onnx_backend, 'np', object())
    monkeypatch.setattr(onnx_backend, 'Image', object())

    load_calls = []

    def _capture_load(model_name):
        load_calls.append(model_name)

    monkeypatch.setattr(engine, '_load_model', _capture_load)

    asyncio.run(engine.initialize())

    assert load_calls == ['ssd-mobilenet-v2', 'mobilenetv3', 'scrfd-2.5g']


def test_load_model_uses_model_registry_and_runtime_session(monkeypatch, tmp_path):
    engine = ONNXVisionEngine(_make_config())

    fake_ort = types.SimpleNamespace()
    fake_ort.InferenceSession = MagicMock(return_value=object())
    monkeypatch.setattr(onnx_backend, 'ort', fake_ort)

    metadata = ModelMetadata(
        type='vision.classification',
        key='mobilenetv3',
        label='MobileNetV3',
        url='https://example.com/model.onnx',
        folder='mobilenetv3',
        required=['model.onnx'],
        kind='classification',
        inputShape=[1, 3, 224, 224],
    )

    manager = MagicMock()
    manager.load_model.return_value = metadata
    manager.get_model_cache_dir_for_type.return_value = tmp_path
    engine.manager = manager

    monkeypatch.setattr(engine, '_load_labels', lambda _dir, _kind: ['cat', 'dog'])

    engine._load_model('mobilenetv3')

    fake_ort.InferenceSession.assert_called_once_with(
        str(Path(tmp_path) / 'mobilenetv3' / 'model.onnx'),
        providers=['CPUExecutionProvider'],
    )
    assert 'mobilenetv3' in engine.models
    assert engine.models['mobilenetv3'].labels == ['cat', 'dog']


def test_load_model_without_onnx_file_raises(monkeypatch, tmp_path):
    engine = ONNXVisionEngine(_make_config())

    metadata = ModelMetadata(
        type='vision.classification',
        key='mobilenetv3',
        label='MobileNetV3',
        url='https://example.com/model.bin',
        folder='mobilenetv3',
        required=['labels.txt'],
        kind='classification',
        inputShape=[1, 3, 224, 224],
    )

    manager = MagicMock()
    manager.load_model.return_value = metadata
    manager.get_model_cache_dir_for_type.return_value = tmp_path
    engine.manager = manager

    with pytest.raises(TJBotError, match='No ONNX file found'):
        engine._load_model('mobilenetv3')


def test_detect_objects_uses_mocked_runtime_and_postprocess(monkeypatch):
    engine = ONNXVisionEngine(_make_config())

    session = _FakeSession(outputs=[[[0.0]]], output_names=['detection_out'])
    engine.models['ssd-mobilenet-v2'] = LoadedModel(
        session=session,
        labels=['person'],
        input_shape=[1, 3, 640, 640],
        kind='detection',
    )

    monkeypatch.setattr(engine, '_preprocess_image', lambda _img, _size: 'tensor')
    monkeypatch.setattr(
        engine,
        '_postprocess_detection',
        lambda outputs, labels, output_names, threshold: [
            {
                'label': labels[0],
                'confidence': threshold,
                'bbox': (0.1, 0.2, 0.3, 0.4),
            }
        ],
    )

    result = asyncio.run(engine.detect_objects(b'image-bytes'))

    assert result[0]['label'] == 'person'
    assert result[0]['confidence'] == 0.5


def test_classify_image_uses_mocked_runtime_and_postprocess(monkeypatch):
    engine = ONNXVisionEngine(_make_config())

    session = _FakeSession(outputs=[[[0.1, 0.9]]], output_names=['class_out'])
    engine.models['mobilenetv3'] = LoadedModel(
        session=session,
        labels=['cat', 'dog'],
        input_shape=[1, 3, 224, 224],
        kind='classification',
    )

    monkeypatch.setattr(engine, '_preprocess_image', lambda _img, _size: 'tensor')
    monkeypatch.setattr(
        engine,
        '_postprocess_classification',
        lambda outputs, labels, threshold, output_names: [
            {'label': labels[1], 'confidence': threshold + 0.1}
        ],
    )

    result = asyncio.run(engine.classify_image(b'image-bytes'))

    assert result == [{'label': 'dog', 'confidence': 0.5}]


def test_detect_faces_uses_mocked_runtime_and_postprocess(monkeypatch):
    engine = ONNXVisionEngine(_make_config())

    session = _FakeSession(outputs=[[[0.1]]], output_names=['face_out'])
    engine.models['scrfd-2.5g'] = LoadedModel(
        session=session,
        labels=[],
        input_shape=[1, 3, 640, 640],
        kind='face-detection',
    )

    monkeypatch.setattr(engine, '_preprocess_face_image', lambda _img, _size: 'tensor')
    monkeypatch.setattr(
        engine,
        '_postprocess_face_detection',
        lambda _outputs, threshold, _size: [
            {
                'boundingBox': (0.2, 0.2, 0.2, 0.2),
                'confidence': threshold,
                'landmarks': [],
            }
        ],
    )

    result = asyncio.run(engine.detect_faces(b'image-bytes'))

    assert result['isFaceDetected'] is True
    assert len(result['metadata']) == 1


def test_onnx_requires_initialize_before_inference():
    engine = ONNXVisionEngine(_make_config())

    with pytest.raises(TJBotError, match='not initialized'):
        asyncio.run(engine.detect_objects(b'image'))
