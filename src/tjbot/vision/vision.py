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

    async def initialize(self, config: SeeConfig) -> None:
        self.vision_config = config
        self.vision_engine = await create_vision_engine(config)
        await self.vision_engine.initialize()

    async def detect_objects(self, image: ImageInput) -> List[ObjectDetectionResult]:
        if not self.vision_engine:
            raise RuntimeError('Vision engine not initialized. Call initialize() before detecting objects.')
        return await self.vision_engine.detect_objects(image)

    async def classify_image(self, image: ImageInput) -> List[ImageClassificationResult]:
        if not self.vision_engine:
            raise RuntimeError('Vision engine not initialized. Call initialize() before classifying images.')
        return await self.vision_engine.classify_image(image)

    async def detect_faces(self, image: ImageInput) -> FaceDetectionResult:
        if not self.vision_engine:
            raise RuntimeError('Vision engine not initialized. Call initialize() before detecting faces.')
        return await self.vision_engine.detect_faces(image)

    async def describe_image(self, image: ImageInput) -> ImageDescriptionResult:
        if not self.vision_engine:
            raise RuntimeError('Vision engine not initialized. Call initialize() before describing images.')
        return await self.vision_engine.describe_image(image)

    async def cleanup(self) -> None:
        if self.vision_engine:
            await self.vision_engine.cleanup()
            self.vision_engine = None
