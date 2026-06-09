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

from abc import ABC, abstractmethod
from typing import Any, List, Literal, NoReturn, Optional, Tuple, TypedDict, Union

from ..config.config_types import (
    SeeBackendAzureConfig,
    SeeBackendGoogleCloudConfig,
    SeeBackendLocalConfig,
    SeeConfig,
)
from ..utils.errors import TJBotError

ImageInput = Union[bytes, str]


class ObjectDetectionResult(TypedDict):
    label: str
    confidence: float
    bbox: Tuple[float, float, float, float]


class ImageClassificationResult(TypedDict):
    label: str
    confidence: float


class ImageDescriptionResult(TypedDict):
    description: str
    confidence: float


class Landmark(TypedDict, total=False):
    x: float
    y: float
    type: str


class FaceHeadPose(TypedDict):
    roll: float
    yaw: float
    pitch: float


class FaceQualityMetrics(TypedDict, total=False):
    blurValue: float
    exposure: Literal["underExposed", "goodExposure", "overExposed"]
    noise: float


class FaceOcclusion(TypedDict):
    eyeOccluded: bool
    foreheadOccluded: bool
    mouthOccluded: bool


class FaceDetectionMetadata(TypedDict, total=False):
    boundingBox: Tuple[float, float, float, float]
    confidence: float
    landmarks: List[Landmark]
    headPose: FaceHeadPose
    qualityMetrics: FaceQualityMetrics
    occlusion: FaceOcclusion


class FaceDetectionResult(TypedDict):
    isFaceDetected: bool
    metadata: List[FaceDetectionMetadata]


class VisionEngine(ABC):
    def __init__(self, config: Optional[Any] = None):
        self.config: Any = config if config is not None else {}

    @abstractmethod
    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        return

    @abstractmethod
    def detect_objects(self, image: ImageInput) -> List[ObjectDetectionResult]:
        pass

    @abstractmethod
    def classify_image(self, image: ImageInput) -> List[ImageClassificationResult]:
        pass

    @abstractmethod
    def detect_faces(self, image: ImageInput) -> FaceDetectionResult:
        pass

    @abstractmethod
    def describe_image(self, image: ImageInput) -> ImageDescriptionResult:
        pass


class NoneVisionEngine(VisionEngine):
    def initialize(self) -> None:
        return

    def _disabled(self) -> NoReturn:
        raise TJBotError(
            "Vision is disabled. Configure a vision backend (local, google-cloud-vision, or azure-vision) to use image analysis."
        )

    def detect_objects(self, image: ImageInput) -> List[ObjectDetectionResult]:
        _ = image
        self._disabled()

    def classify_image(self, image: ImageInput) -> List[ImageClassificationResult]:
        _ = image
        self._disabled()

    def detect_faces(self, image: ImageInput) -> FaceDetectionResult:
        _ = image
        self._disabled()

    def describe_image(self, image: ImageInput) -> ImageDescriptionResult:
        _ = image
        self._disabled()


def _get_see_backend_config(
    see_config: SeeConfig, backend_type: str
) -> Optional[object]:
    if see_config.backend is None:
        return None
    if backend_type == "local":
        return see_config.backend.local
    if backend_type == "google-cloud-vision":
        return see_config.backend.google_cloud_vision
    if backend_type == "azure-vision":
        return see_config.backend.azure_vision
    return None


def create_vision_engine(see_config: SeeConfig) -> VisionEngine:
    backend = (
        see_config.backend.type
        if see_config.backend and see_config.backend.type
        else "local"
    )

    try:
        if backend == "none":
            return NoneVisionEngine()

        if backend == "local":
            from .backends.onnx import ONNXVisionEngine

            config = _get_see_backend_config(see_config, backend)
            return ONNXVisionEngine(
                config if isinstance(config, SeeBackendLocalConfig) else None
            )

        if backend == "google-cloud-vision":
            from .backends.google_cloud_vision import GoogleCloudVisionEngine

            config = _get_see_backend_config(see_config, backend)
            return GoogleCloudVisionEngine(
                config if isinstance(config, SeeBackendGoogleCloudConfig) else None
            )

        if backend == "azure-vision":
            from .backends.azure_vision import AzureVisionEngine

            config = _get_see_backend_config(see_config, backend)
            return AzureVisionEngine(
                config if isinstance(config, SeeBackendAzureConfig) else None
            )

        raise TJBotError(f"Unknown Vision backend type: {backend}")
    except Exception as error:
        if isinstance(error, TJBotError):
            raise
        raise TJBotError(
            f'Failed to load Vision backend "{backend}". Ensure dependencies are installed.',
            cause=error,
        )
