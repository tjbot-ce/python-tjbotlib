import pytest
from tjbot.utils.model_registry import ModelRegistry, ModelMetadata
from tjbot.utils.errors import TJBotError


def test_model_registry_loads_metadata_file():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models()
    assert len(models) > 0


def test_model_registry_contains_known_node_parity_models():
    registry = ModelRegistry.get_instance()

    object_detection = registry.lookup_model("ssd-mobilenet-v2")
    face_detection = registry.lookup_model("scrfd-2.5g")

    assert object_detection.type == "vision.object-recognition"
    assert face_detection.type == "vision.face-detection"


def test_model_registry_cache_dir_layout():
    registry = ModelRegistry.get_instance()

    vision_dir = registry.get_model_cache_dir_for_type("vision.object-recognition")
    stt_dir = registry.get_model_cache_dir_for_type("stt")

    assert str(vision_dir).endswith("/.tjbot/models/vision")
    assert str(stt_dir).endswith("/.tjbot/models/stt")


# ---------------------------------------------------------------------------
# lookup_models with model_type filter
# ---------------------------------------------------------------------------


def test_lookup_models_returns_all_models_when_no_filter():
    registry = ModelRegistry.get_instance()
    all_models = registry.lookup_models()
    assert len(all_models) > 0


def test_lookup_models_filters_by_stt_type():
    registry = ModelRegistry.get_instance()
    stt_models = registry.lookup_models(model_type="stt")
    assert len(stt_models) > 0
    for m in stt_models:
        assert m.type == "stt"


def test_lookup_models_filters_by_tts_type():
    registry = ModelRegistry.get_instance()
    tts_models = registry.lookup_models(model_type="tts")
    assert len(tts_models) > 0
    for m in tts_models:
        assert m.type == "tts"


def test_lookup_models_filters_by_vision_face_detection():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(model_type="vision.face-detection")
    assert len(models) > 0
    for m in models:
        assert m.type == "vision.face-detection"


def test_lookup_models_filters_by_vision_object_recognition():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(model_type="vision.object-recognition")
    assert len(models) > 0
    for m in models:
        assert m.type == "vision.object-recognition"


def test_lookup_models_returns_empty_list_for_unknown_type():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(model_type="not.a.real.type")
    assert models == []


# ---------------------------------------------------------------------------
# lookup_model (single model)
# ---------------------------------------------------------------------------


def test_lookup_model_returns_stt_model():
    registry = ModelRegistry.get_instance()
    model = registry.lookup_model("moonshine-tiny")
    assert model is not None
    assert model.key == "moonshine-tiny"
    assert model.type == "stt"


def test_lookup_model_returns_tts_model():
    registry = ModelRegistry.get_instance()
    model = registry.lookup_model("vits-piper-en_US-ryan-low")
    assert model is not None
    assert model.key == "vits-piper-en_US-ryan-low"
    assert model.type == "tts"


def test_lookup_model_returns_vad_model():
    registry = ModelRegistry.get_instance()
    model = registry.lookup_model("silero-vad")
    assert model is not None
    assert model.type == "vad"


def test_lookup_model_raises_for_unknown_key():
    registry = ModelRegistry.get_instance()
    with pytest.raises(TJBotError, match="not found in registry"):
        registry.lookup_model("this-model-does-not-exist")


# ---------------------------------------------------------------------------
# is_model_downloaded
# ---------------------------------------------------------------------------


def test_is_model_downloaded_raises_for_unknown_key():
    registry = ModelRegistry.get_instance()
    with pytest.raises(TJBotError, match="not found in registry"):
        registry.is_model_downloaded("nonexistent-model-key")


def test_is_model_downloaded_returns_bool():
    registry = ModelRegistry.get_instance()
    result = registry.is_model_downloaded("moonshine-tiny")
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# register_model
# ---------------------------------------------------------------------------


def test_register_model_adds_to_registry():
    registry = ModelRegistry()
    custom_model = ModelMetadata(
        type="stt",
        key="my-custom-test-model",
        label="Custom Test Model",
        url="https://example.com/model.tar.bz2",
        folder="my-custom-test-model",
        required=["model.onnx"],
    )
    registry.register_model(custom_model)
    result = registry.lookup_model("my-custom-test-model")
    assert result is not None
    assert result.key == "my-custom-test-model"
    assert result.label == "Custom Test Model"


def test_register_model_appears_in_lookup_models():
    registry = ModelRegistry()
    custom_model = ModelMetadata(
        type="tts",
        key="my-custom-tts-model",
        label="Custom TTS Model",
        url="https://example.com/tts-model.tar.bz2",
        folder="my-custom-tts-model",
        required=["model.onnx"],
    )
    registry.register_model(custom_model)
    all_models = registry.lookup_models()
    keys = [m.key for m in all_models]
    assert "my-custom-tts-model" in keys


# ---------------------------------------------------------------------------
# Model metadata fields
# ---------------------------------------------------------------------------


def test_model_metadata_has_required_fields():
    registry = ModelRegistry.get_instance()
    model = registry.lookup_model("ssd-mobilenet-v2")
    assert model.key is not None
    assert model.type is not None
    assert model.label is not None
    assert model.url is not None
    assert model.folder is not None
    assert isinstance(model.required, list)


def test_lookupmodels_returns_an_array_of_vad_models_with_at_least_one():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(model_type="vad")
    assert isinstance(models, list)
    assert len(models) > 0


def test_mobilenetv3_classification_model_exists_in_supported_models():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(model_type="vision.classification")
    model = next((m for m in models if m.key == "mobilenetv3"), None)
    assert model is not None
    assert model.type == "vision.classification"


def test_lookupmodels_with_installedonly_true_returns_only_installed_stt_models():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(model_type="stt", installed_only=True)
    assert isinstance(models, list)
    for model in models:
        assert registry.is_model_downloaded(model.key) is True


def test_lookupmodels_with_installedonly_true_returns_only_installed_tts_models():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(model_type="tts", installed_only=True)
    assert isinstance(models, list)
    for model in models:
        assert registry.is_model_downloaded(model.key) is True


def test_lookupmodels_with_installedonly_true_returns_only_installed_vad_models():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(model_type="vad", installed_only=True)
    assert isinstance(models, list)
    for model in models:
        assert registry.is_model_downloaded(model.key) is True


def test_lookupmodels_with_installedonly_true_returns_only_installed_vision_models():
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(
        model_type="vision.object-recognition", installed_only=True
    )
    assert isinstance(models, list)
    for model in models:
        assert registry.is_model_downloaded(model.key) is True


def test_loadmodel_throws_error_for_non_existent_model():
    registry = ModelRegistry.get_instance()
    with pytest.raises(TJBotError, match="not found in registry"):
        registry.load_model("non-existent-model-xyz")


def test_downloadmodel_throws_error_for_non_existent_model():
    registry = ModelRegistry.get_instance()
    with pytest.raises(TJBotError, match="not found in registry"):
        registry.download_model("non-existent-model-xyz")
