from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from jsonschema import ValidationError, validators
import yaml

from ..utils.errors import TJBotError
from ..utils import ModelRegistry
from ..utils.model_registry import ModelMetadata
from ..utils.logging import get_logger, LogEmoji
from .config_types import (
    TJBotConfigSchema,
    LogConfig,
    HardwareConfig,
    ListenConfig,
    SeeConfig,
    ShineConfig,
    SpeakConfig,
    WaveConfig,
)

_logger = get_logger(__name__)
_EMO = LogEmoji.CONFIG


class TJBotConfig:
    """
    TJBotConfig manages loading and parsing TJBot configuration from TOML files.
    It provides access to configuration via structured interfaces.
    """

    def __init__(
        self,
        override_config: Optional[Dict[str, Any]] = None,
        recipe_config_path: str = "recipe.toml",
    ):
        self._config: TJBotConfigSchema

        # Paths
        pkg_dir = Path(__file__).parent
        self.default_config_path = self._resolve_shared_asset("tjbot.default.toml", pkg_dir / "vendor" / "tjbot.default.toml")
        self.schema_config_path = self._resolve_shared_asset(
            "tjbot-config.schema.yaml",
            pkg_dir / "vendor" / "tjbot-config.schema.yaml",
        )
        self.local_config_path = Path.home() / ".tjbot" / "tjbot.toml"
        self.recipe_config_path = Path(recipe_config_path)

        # Load default config
        default_config = self._load_internal_config()

        # Load user config from ~/.tjbot/tjbot.toml if it exists
        home_config = self._load_home_config()

        # Load recipe config from recipe.toml if it exists
        recipe_config = self._load_recipe_config()

        # Merge general configuration in cascade order: default -> home -> overrides
        merged_config = self._deep_merge(default_config, home_config or {}, override_config or {})

        # Merge recipe config into the recipe section
        if recipe_config:
            merged_config["recipe"] = self._deep_merge(merged_config.get("recipe") or {}, recipe_config)
        else:
            merged_config.setdefault("recipe", {})

        self._validate_against_schema(merged_config)

        try:
            self._config = TJBotConfigSchema(**merged_config)
        except Exception as e:
            raise TJBotError("invalid TJBot configuration", cause=e)

        # Register user-defined models from [models] section
        models = self._config.models
        if models:
            registry = ModelRegistry.get_instance()
            for model in models:
                metadata = ModelMetadata(
                    type=model.get("type", ""),
                    key=model.get("key", ""),
                    label=model.get("label", model.get("key", "")),
                    url=model.get("url", ""),
                    folder=model.get("folder", model.get("key", "")),
                    required=list(model.get("required", [])),
                    kind=model.get("kind"),
                    labelUrl=model.get("labelUrl"),
                    inputShape=model.get("inputShape"),
                )
                registry.register_model(metadata)
                _logger.debug(f"{_EMO} Registered custom ML model: {metadata.key}")

        # Validate vision backend config when configured
        # Validate vision backend config when configured
        self._validate_vision_backend_config()

        _logger.debug(f"{_EMO} TJBot configuration loaded successfully")

    @property
    def config(self) -> TJBotConfigSchema:
        """The full parsed configuration schema."""
        return self._config

    @property
    def log(self) -> LogConfig:
        return self._config.log or LogConfig()

    @property
    def hardware(self) -> HardwareConfig:
        return self._config.hardware or HardwareConfig()

    @property
    def listen(self) -> ListenConfig:
        return self._config.listen or ListenConfig()

    @property
    def see(self) -> SeeConfig:
        return self._config.see or SeeConfig()

    @property
    def shine(self) -> ShineConfig:
        return self._config.shine or ShineConfig()

    @property
    def speak(self) -> SpeakConfig:
        return self._config.speak or SpeakConfig()

    @property
    def wave(self) -> WaveConfig:
        return self._config.wave or WaveConfig()

    @property
    def recipe(self) -> Dict[str, Any]:
        return self._config.recipe or {}

    def get(self, key: str) -> Any:
        """Get raw configuration value by key (for backward compatibility)."""
        return getattr(self._config, key, None)

    def _resolve_shared_asset(self, filename: str, bundled_path: Path) -> Path:
        repo_root = Path(__file__).resolve().parents[3]
        vendor_path = repo_root / "vendor" / "tjbot-config" / filename
        if vendor_path.exists():
            return vendor_path
        return bundled_path

    def _load_internal_config(self) -> Dict[str, Any]:
        """Load internal default TOML configuration."""
        _logger.debug(f"{_EMO} loading default TJBot configuration TOML from {self.default_config_path}")
        return self._load_toml_file(self.default_config_path)

    def _load_home_config(self) -> Optional[Dict[str, Any]]:
        """Load user configuration from ~/.tjbot/tjbot.toml if it exists."""
        if self.local_config_path.exists() and self.local_config_path.is_file():
            _logger.debug(f"{_EMO} loading user TJBot configuration from {self.local_config_path}")
            try:
                return self._load_toml_file(self.local_config_path)
            except Exception as e:
                raise TJBotError(f"unable to read tjbot configuration from {self.local_config_path}: {e}")
        else:
            _logger.debug(f"{_EMO} user configuration file {self.local_config_path} not found, skipping")
            return None

    def _load_recipe_config(self) -> Optional[Dict[str, Any]]:
        """Load recipe-specific configuration from recipe.toml if it exists.
        The entire file content is treated as recipe configuration."""
        if self.recipe_config_path.exists() and self.recipe_config_path.is_file():
            _logger.debug(f"{_EMO} loading recipe configuration from {self.recipe_config_path}")
            try:
                return self._load_toml_file(self.recipe_config_path)
            except Exception as e:
                raise TJBotError(f"unable to read recipe configuration from {self.recipe_config_path}: {e}")
        else:
            _logger.debug(f"{_EMO} recipe configuration file {self.recipe_config_path} not found, skipping")
            return None

    def _validate_against_schema(self, config: Dict[str, Any]) -> None:
        if not self.schema_config_path.exists():
            return

        try:
            with open(self.schema_config_path, "r", encoding="utf-8") as schema_file:
                schema = yaml.safe_load(schema_file)
        except Exception as e:
            raise TJBotError(
                f"unable to read TJBot config schema from {self.schema_config_path}: {e}"
            )

        try:
            validator_cls = validators.validator_for(schema)
            validator_cls.check_schema(schema)
            validator = validator_cls(schema)
            errors = sorted(validator.iter_errors(config), key=lambda err: list(err.path))
            if errors:
                raise ValidationError(errors[0].message)
        except ValidationError as e:
            raise TJBotError("invalid TJBot configuration", cause=e)

    def _load_toml_file(self, path: Path) -> Dict[str, Any]:
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
            return self._clean_config(data)
        except Exception as e:
            raise TJBotError(f"unable to read TOML from {path}: {e}")

    def _deep_merge(self, *sources: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge multiple configuration objects.
        Later objects override earlier ones, but only at the leaf level."""
        result: Dict[str, Any] = {}
        for source in sources:
            for key, value in source.items():
                result_value = result.get(key)
                # If the value is an array, replace it entirely (no merging)
                if isinstance(value, list):
                    result[key] = value
                # If both values are plain objects, merge them recursively
                elif self._is_plain_object(value) and self._is_plain_object(result_value):
                    result[key] = self._deep_merge(result_value, value)
                # Otherwise, replace the value
                else:
                    result[key] = value
        return result

    def _is_plain_object(self, value: Any) -> bool:
        """Check if a value is a plain dict (not None, not a list, etc.)"""
        return isinstance(value, dict)

    def _clean_config(self, obj: Any) -> Any:
        """Clean configuration object to remove non-string keys."""
        if obj is None:
            return obj
        if isinstance(obj, list):
            return [self._clean_config(item) for item in obj]
        if isinstance(obj, dict):
            return {k: self._clean_config(v) for k, v in obj.items() if isinstance(k, str)}
        return obj

    def _validate_vision_local_models(self, local_config: Dict[str, Any]) -> None:
        """Validate vision local backend models are properly configured."""
        models = [
            {"field": "object_detection_model", "expected_kind": "detection"},
            {"field": "image_classification_model", "expected_kind": "classification"},
            {"field": "face_detection_model", "expected_kind": "face-detection"},
        ]
        for model in models:
            if not local_config.get(model["field"]):
                raise TJBotError(f"Vision local backend: {model['field']} is required but not configured")

        confidence_fields = [
            "object_detection_confidence",
            "image_classification_confidence",
            "face_detection_confidence",
        ]
        for field in confidence_fields:
            value = local_config.get(field)
            if value is not None and (not isinstance(value, (int, float)) or value < 0 or value > 1):
                raise TJBotError(f"Vision local backend: {field} must be a number between 0.0 and 1.0")

    def _validate_vision_backend_config(self) -> None:
        """Validate vision backend configuration for all backend types."""
        see = self._config.see
        if see is None:
            return

        backend = see.backend
        if not backend:
            return

        if backend.type == "local" and backend.local is not None:
            self._validate_vision_local_models(backend.local.model_dump())
            return

        if backend.type == "google-cloud-vision" and backend.google_cloud_vision is not None:
            self._validate_vision_thresholds(
                "google-cloud-vision",
                backend.google_cloud_vision.model_dump(),
                ["object_detection_confidence", "image_classification_confidence", "face_detection_confidence"],
            )
            return

        if backend.type == "azure-vision" and backend.azure_vision is not None:
            self._validate_vision_thresholds(
                "azure-vision",
                backend.azure_vision.model_dump(),
                ["object_detection_confidence", "image_classification_confidence"],
            )

    def _validate_vision_thresholds(self, backend_name: str, config: Dict[str, Any], fields: List[str]) -> None:
        """Validate confidence thresholds in a backend config object."""
        for field in fields:
            value = config.get(field)
            if value is not None and (not isinstance(value, (int, float)) or value < 0 or value > 1):
                raise TJBotError(f"Vision {backend_name} backend: {field} must be a number between 0.0 and 1.0")

