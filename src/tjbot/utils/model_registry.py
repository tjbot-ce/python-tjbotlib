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

from __future__ import annotations

import logging
import os
import shutil
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union
from urllib.parse import urlparse

import requests
import yaml

from .errors import TJBotError

logger = logging.getLogger(__name__)


ModelType = Literal[
    "stt",
    "tts",
    "vad",
    "vision.object-recognition",
    "vision.classification",
    "vision.face-detection",
    "vision.image-description",
]

STTModelKind = Literal[
    "offline",
    "offline-whisper",
    "streaming-zipformer",
    "streaming-paraformer",
    "streaming",
]
TTSModelKind = Literal["vits-piper", "tacotron", "fastpitch", "streaming"]
VisionModelKind = Literal[
    "detection", "classification", "face-detection", "image-description"
]
ModelKind = Union[STTModelKind, TTSModelKind, VisionModelKind]


@dataclass
class ModelMetadata:
    type: ModelType
    key: str
    label: str
    url: str
    folder: str
    required: List[str]
    kind: Optional[ModelKind] = None
    labelUrl: Optional[str] = None
    inputShape: Optional[List[int]] = None


class ModelRegistry:
    _instance: Optional["ModelRegistry"] = None

    _PROGRESS_WIDTH = 20
    _PROGRESS_COMPLETE = "█"
    _PROGRESS_INCOMPLETE = "░"

    def __init__(self):
        self.registered_models: Dict[str, ModelMetadata] = {}
        self._metadata_loaded = False
        self._load_metadata()

    @classmethod
    def get_instance(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = ModelRegistry()
        return cls._instance

    def _registry_yaml_path(self) -> Path:
        repo_root = Path(__file__).resolve().parents[3]
        vendor_path = repo_root / "vendor" / "tjbot-config" / "model-registry.yaml"
        if vendor_path.exists():
            return vendor_path
        return Path(__file__).resolve().parent.parent / "config" / "model-registry.yaml"

    def _load_metadata(self) -> None:
        if self._metadata_loaded:
            return

        yaml_path = self._registry_yaml_path()
        if not yaml_path.exists():
            raise TJBotError(f"Model registry metadata file not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        models = data.get("models", [])
        for model in models:
            key = model.get("key")
            if not key:
                raise TJBotError("Model entry missing key")

            metadata = ModelMetadata(
                type=model.get("type", ""),
                key=key,
                label=model.get("label", key),
                url=model.get("url", ""),
                folder=model.get("folder", key),
                required=list(model.get("required", [])),
                kind=model.get("kind"),
                labelUrl=model.get("labelUrl"),
                inputShape=model.get("inputShape"),
            )
            self.register_model(metadata)

        self._metadata_loaded = True

    def register_model(self, model: ModelMetadata) -> None:
        self.registered_models[model.key] = model

    def lookup_model(self, model_key: str) -> ModelMetadata:
        model = self.registered_models.get(model_key)
        if not model:
            raise TJBotError(f'Model with key "{model_key}" not found in registry')
        return model

    def lookup_models(
        self, model_type: Optional[ModelType] = None, installed_only: bool = False
    ) -> List[ModelMetadata]:
        candidates = list(self.registered_models.values())
        if model_type is not None:
            candidates = [m for m in candidates if m.type == model_type]

        if installed_only:
            candidates = [m for m in candidates if self.is_model_downloaded(m.key)]

        return candidates

    def get_model_cache_dir(self) -> Path:
        return Path.home() / ".tjbot" / "models"

    def get_model_cache_dir_for_type(self, model_type: str) -> Path:
        cache_subdir = "vision" if model_type.startswith("vision.") else model_type
        return self.get_model_cache_dir() / cache_subdir

    def is_model_downloaded(self, model_key: str) -> bool:
        model = self.lookup_model(model_key)
        model_path = self.get_model_cache_dir_for_type(model.type) / model.folder
        if not model_path.exists():
            return False
        return all(
            (model_path / required_file).exists() for required_file in model.required
        )

    def load_model(self, model_key: str) -> ModelMetadata:
        model = self.lookup_model(model_key)
        if not self.is_model_downloaded(model_key):
            self.download_model(model_key)
        return model

    def _write_progress_line(
        self, action: str, transferred_bytes: int, total_bytes: int
    ) -> None:
        if total_bytes <= 0:
            return

        ratio = min(max(transferred_bytes / total_bytes, 0.0), 1.0)
        complete = int(ratio * self._PROGRESS_WIDTH)
        bar = self._PROGRESS_COMPLETE * complete + self._PROGRESS_INCOMPLETE * (
            self._PROGRESS_WIDTH - complete
        )
        transferred_mb = transferred_bytes / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)
        sys.stderr.write(
            f"\r{action} [{bar}] {ratio * 100:3.0f}% | {transferred_mb:.1f}/{total_mb:.1f} MB"
        )
        sys.stderr.flush()

    def _finish_progress_line(self) -> None:
        sys.stderr.write("\n")
        sys.stderr.flush()

    def _download_file(self, url: str, destination: Path, max_retries: int = 3) -> None:
        """Download a file from URL with retry logic and progress bar."""
        destination.parent.mkdir(parents=True, exist_ok=True)

        parsed = urlparse(url)
        if parsed.scheme == "file":
            source = Path(parsed.path)
            if not source.exists():
                raise TJBotError(f"File URL source not found: {url}")

            total_size = source.stat().st_size
            transferred = 0
            with open(source, "rb") as src, open(destination, "wb") as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
                    transferred += len(chunk)
                    self._write_progress_line("Copying", transferred, total_size)

            if total_size > 0:
                self._finish_progress_line()
            return

        # Download with retry logic
        attempt = 0
        last_error = None

        while attempt < max_retries:
            try:
                logger.info(
                    f"Downloading from {url} (attempt {attempt + 1}/{max_retries})"
                )

                response = requests.get(url, timeout=60, stream=True)
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                transferred = 0

                with open(destination, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            file.write(chunk)
                            transferred += len(chunk)
                            if total_size > 0:
                                self._write_progress_line(
                                    "Downloading", transferred, total_size
                                )

                if total_size > 0:
                    self._finish_progress_line()

                logger.info("Download complete")
                return

            except Exception as e:
                last_error = e
                attempt += 1
                if attempt < max_retries:
                    delay = min(2**attempt, 10)
                    logger.info(
                        f"Retrying download in {delay}s... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                else:
                    logger.warning(
                        f"Download failed (attempt {attempt}/{max_retries}): {e}"
                    )

        if last_error:
            logger.error(f"Download failed after {max_retries} attempts")
            raise last_error

    def _extract_tar_bz2(self, archive_path: Path, destination_dir: Path) -> None:
        """Extract a tar.bz2 archive with logging."""
        destination_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Extracting archive...")
        with tarfile.open(archive_path, mode="r:bz2") as archive:
            archive.extractall(path=destination_dir)
        logger.info("Extraction complete")

    def download_model(self, model_key: str) -> None:
        """Download and cache a model."""
        model = self.lookup_model(model_key)
        cache_dir = self.get_model_cache_dir_for_type(model.type)
        model_path = cache_dir / model.folder

        if self.is_model_downloaded(model_key):
            return

        cache_dir.mkdir(parents=True, exist_ok=True)

        temp_archive = Path("/tmp") / f"{model.key}-download"
        self._download_file(model.url, temp_archive)

        if model.url.endswith(".tar.bz2"):
            self._extract_tar_bz2(temp_archive, cache_dir)
            if temp_archive.exists():
                temp_archive.unlink()
        else:
            model_path.mkdir(parents=True, exist_ok=True)
            file_name = os.path.basename(urlparse(model.url).path)
            if not file_name:
                raise TJBotError(
                    f"Cannot determine file name for model URL: {model.url}"
                )
            target_path = model_path / file_name
            shutil.copy2(temp_archive, target_path)
            if temp_archive.exists():
                temp_archive.unlink()

        if model.type.startswith("vision.") and model.labelUrl:
            label_file_name = os.path.basename(urlparse(model.labelUrl).path)
            if label_file_name:
                label_target_path = model_path / label_file_name
                if not label_target_path.exists():
                    self._download_file(model.labelUrl, label_target_path)

        if not self.is_model_downloaded(model_key):
            raise TJBotError(
                f'Model "{model_key}" download incomplete: required files missing'
            )

        logger.info(f'Model "{model_key}" downloaded and extracted to {model_path}')
