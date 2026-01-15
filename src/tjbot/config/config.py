from typing import Any, Dict, Optional
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from ..error import TJBotError
from .models import TJBotConfigModel, LogConfig, HardwareConfig, ListenConfig, SeeConfig, ShineConfig, SpeakConfig, WaveConfig

class TJBotConfig:
    """
    TJBotConfig manages loading and parsing TJBot configuration from TOML files.
    """

    def __init__(self, override_config: Optional[Dict[str, Any]] = None):
        self.config_model: TJBotConfigModel

        # Paths
        pkg_dir = Path(__file__).parent
        self.default_config_path = pkg_dir / "tjbot.default.toml"
        self.local_config_path = Path("tjbot.toml")

        # Load configs
        default_config = self._load_toml_file(self.default_config_path)

        user_config: Dict[str, Any] = {}
        if self.local_config_path.exists() and self.local_config_path.is_file():
            try:
                user_config = self._load_toml_file(self.local_config_path)
            except Exception as e:
                raise TJBotError(f"unable to read tjbot configuration from {self.local_config_path}: {e}")

        # Merge configs: default -> user -> override
        merged_config = self._merge_configs(default_config, user_config)
        if override_config:
            merged_config = self._merge_configs(merged_config, override_config)

        try:
            self.config_model = TJBotConfigModel(**merged_config)
        except Exception as e:
            raise TJBotError("invalid TJBot configuration", cause=e)

    @property
    def log(self) -> LogConfig:
        return self.config_model.log or LogConfig()

    @property
    def hardware(self) -> HardwareConfig:
        return self.config_model.hardware or HardwareConfig()

    @property
    def listen(self) -> ListenConfig:
        return self.config_model.listen or ListenConfig()

    @property
    def see(self) -> SeeConfig:
        return self.config_model.see or SeeConfig()

    @property
    def shine(self) -> ShineConfig:
        return self.config_model.shine or ShineConfig()

    @property
    def speak(self) -> SpeakConfig:
        return self.config_model.speak or SpeakConfig()

    @property
    def wave(self) -> WaveConfig:
        return self.config_model.wave or WaveConfig()

    @property
    def recipe(self) -> Dict[str, Any]:
        return self.config_model.recipe or {}

    def _load_toml_file(self, path: Path) -> Dict[str, Any]:
        try:
            with open(path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            raise TJBotError(f"unable to read TOML from {path}: {e}")

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        merged = base.copy()
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        return merged
