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

import io
from typing import Any, List, Optional

from ...config.config_types import SeeBackendAzureConfig
from ...utils.errors import TJBotError
from ...utils.credentials import load_azure_credentials
from ..vision_engine import (
    FaceDetectionResult,
    ImageClassificationResult,
    ImageDescriptionResult,
    ImageInput,
    ObjectDetectionResult,
    VisionEngine,
)

try:
    from azure.cognitiveservices.vision.computervision import ComputerVisionClient
    from msrest.authentication import CognitiveServicesCredentials
except ImportError:
    ComputerVisionClient = None  # type: ignore[assignment,misc]
    CognitiveServicesCredentials = None  # type: ignore[assignment,misc]


class AzureVisionEngine(VisionEngine):
    def __init__(self, config: Optional[SeeBackendAzureConfig] = None):
        super().__init__(config)
        self.client: Any = None
        self.vision_key: Optional[str] = None
        self.vision_endpoint: Optional[str] = None

    def initialize(self) -> None:
        if ComputerVisionClient is None or CognitiveServicesCredentials is None:
            raise TJBotError(
                "azure-cognitiveservices-vision-computervision library not installed. Please install it."
            )

        credentials_path = self.config.credentials_path if self.config else ""
        credentials = load_azure_credentials(credentials_path)
        self.vision_key = credentials.get("visionKey")
        self.vision_endpoint = credentials.get("visionEndpoint")

        if not self.vision_key or not self.vision_endpoint:
            raise TJBotError("Azure Vision visionKey and visionEndpoint are required")

        api_key_credentials = CognitiveServicesCredentials(self.vision_key)
        self.client = ComputerVisionClient(self.vision_endpoint, api_key_credentials)

    def _ensure_client(self):
        if not self.client:
            raise TJBotError(
                "Azure Vision client not initialized. Call initialize() first."
            )

    def _read_image(self, image: ImageInput):
        if isinstance(image, str):
            with open(image, "rb") as file:
                return io.BytesIO(file.read())
        return io.BytesIO(image)

    def _object_detection_threshold(self) -> float:
        if not self.config or self.config.object_detection_confidence is None:
            raise TJBotError(
                "Object detection confidence threshold is not configured for Azure Vision engine"
            )
        return self.config.object_detection_confidence

    def _classification_threshold(self) -> float:
        if not self.config or self.config.image_classification_confidence is None:
            raise TJBotError(
                "Image classification confidence threshold is not configured for Azure Vision engine"
            )
        return self.config.image_classification_confidence

    def detect_objects(self, image: ImageInput) -> List[ObjectDetectionResult]:
        self._ensure_client()
        threshold = self._object_detection_threshold()

        try:
            result = self.client.analyze_image_in_stream(
                self._read_image(image), visual_features=["Objects"]
            )
            output: List[ObjectDetectionResult] = []

            for obj in result.objects or []:
                confidence = float(obj.confidence or 0.0)
                if confidence < threshold:
                    continue

                rect = obj.rectangle
                output.append(
                    {
                        "label": obj.object_property or "unknown",
                        "confidence": confidence,
                        "bbox": (
                            float(rect.x),
                            float(rect.y),
                            float(rect.w),
                            float(rect.h),
                        ),
                    }
                )

            output.sort(key=lambda item: item["confidence"], reverse=True)
            return output
        except Exception as error:
            raise TJBotError(f"Azure Vision API error during object detection: {error}")

    def classify_image(self, image: ImageInput) -> List[ImageClassificationResult]:
        self._ensure_client()
        threshold = self._classification_threshold()

        try:
            result = self.client.analyze_image_in_stream(
                self._read_image(image), visual_features=["Tags"]
            )
            output = [
                {
                    "label": (tag.name or "unknown"),
                    "confidence": float(tag.confidence or 0.0),
                }
                for tag in result.tags or []
                if float(tag.confidence or 0.0) >= threshold
            ]

            output.sort(key=lambda item: item["confidence"], reverse=True)
            return output
        except Exception as error:
            raise TJBotError(f"Azure Vision API error during classification: {error}")

    def detect_faces(self, image: ImageInput) -> FaceDetectionResult:
        _ = image
        raise TJBotError(
            "Face detection is not supported by the Azure Computer Vision service. Please use another backend for face detection."
        )

    def describe_image(self, image: ImageInput) -> ImageDescriptionResult:
        self._ensure_client()

        try:
            result = self.client.analyze_image_in_stream(
                self._read_image(image), visual_features=["Description"]
            )
            captions = (
                result.description.captions if result.description else None
            ) or []
            if not captions:
                return {"description": "", "confidence": 0.0}

            first = captions[0]
            return {
                "description": first.text or "",
                "confidence": float(first.confidence or 0.0),
            }
        except Exception as error:
            raise TJBotError(f"Azure Vision API error during description: {error}")
