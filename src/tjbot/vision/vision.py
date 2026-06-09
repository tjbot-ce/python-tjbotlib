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

from typing import List, Optional

from ..config.config_types import SeeConfig
from .vision_engine import (
    FaceDetectionResult,
    ImageClassificationResult,
    ImageDescriptionResult,
    ImageInput,
    ObjectDetectionResult,
    VisionEngine,
    create_vision_engine,
)


class VisionController:
    def __init__(self):
        self.vision_engine: Optional[VisionEngine] = None
        self.vision_config: Optional[SeeConfig] = None

    def initialize(self, config: SeeConfig) -> None:
        self.vision_config = config
        self.vision_engine = create_vision_engine(config)
        self.vision_engine.initialize()

    def detect_objects(self, image: ImageInput) -> List[ObjectDetectionResult]:
        if not self.vision_engine:
            raise RuntimeError(
                "Vision engine not initialized. Call initialize() before detecting objects."
            )
        return self.vision_engine.detect_objects(image)

    def classify_image(self, image: ImageInput) -> List[ImageClassificationResult]:
        if not self.vision_engine:
            raise RuntimeError(
                "Vision engine not initialized. Call initialize() before classifying images."
            )
        return self.vision_engine.classify_image(image)

    def detect_faces(self, image: ImageInput) -> FaceDetectionResult:
        if not self.vision_engine:
            raise RuntimeError(
                "Vision engine not initialized. Call initialize() before detecting faces."
            )
        return self.vision_engine.detect_faces(image)

    def describe_image(self, image: ImageInput) -> ImageDescriptionResult:
        if not self.vision_engine:
            raise RuntimeError(
                "Vision engine not initialized. Call initialize() before describing images."
            )
        return self.vision_engine.describe_image(image)

    def cleanup(self) -> None:
        if self.vision_engine:
            self.vision_engine.cleanup()
            self.vision_engine = None
