from pathlib import Path

from tjbot.utils.model_registry import ModelRegistry


def test_model_registry_loads_metadata_file():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models()
    assert len(models) > 0


def test_model_registry_contains_known_node_parity_models():
    registry = ModelRegistry.get_instance()

    object_detection = registry.lookup_model('ssd-mobilenet-v2')
    face_detection = registry.lookup_model('scrfd-2.5g')

    assert object_detection.type == 'vision.object-recognition'
    assert face_detection.type == 'vision.face-detection'


def test_model_registry_cache_dir_layout():
    registry = ModelRegistry.get_instance()

    vision_dir = registry.get_model_cache_dir_for_type('vision.object-recognition')
    stt_dir = registry.get_model_cache_dir_for_type('stt')

    assert str(vision_dir).endswith('/.tjbot/models/vision')
    assert str(stt_dir).endswith('/.tjbot/models/stt')
