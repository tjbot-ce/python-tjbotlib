import os
from typing import List, Optional

from ...config.config_types import SeeBackendGoogleCloudConfig
from ...utils.errors import TJBotError
from ...utils.credentials import load_google_cloud_credentials
from ..vision_engine import (
    FaceDetectionResult,
    ImageClassificationResult,
    ImageDescriptionResult,
    ImageInput,
    ObjectDetectionResult,
    VisionEngine,
)

try:
    from google.cloud import vision as google_vision
except ImportError:
    google_vision = None


class GoogleCloudVisionEngine(VisionEngine):
    def __init__(self, config: Optional[SeeBackendGoogleCloudConfig] = None):
        super().__init__(config)
        self.client = None

    async def initialize(self) -> None:
        if google_vision is None:
            raise TJBotError("google-cloud-vision library not installed. Please install it.")

        credentials_path = self.config.credentials_path if self.config else ''
        if credentials_path:
            load_google_cloud_credentials(credentials_path)
        elif not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            # Follow Node behavior: if no explicit path was provided, attempt default file lookup.
            load_google_cloud_credentials('')

        self.client = google_vision.ImageAnnotatorClient()

    def _ensure_client(self):
        if not self.client:
            raise TJBotError('Google Cloud Vision client not initialized. Call initialize() first.')

    def _read_image(self, image: ImageInput):
        if isinstance(image, str):
            with open(image, 'rb') as file:
                return file.read()
        return image

    def _object_detection_threshold(self) -> float:
        if not self.config or self.config.object_detection_confidence is None:
            raise TJBotError('Object detection confidence threshold is not configured for Google Cloud Vision engine')
        return self.config.object_detection_confidence

    def _classification_threshold(self) -> float:
        if not self.config or self.config.image_classification_confidence is None:
            raise TJBotError(
                'Image classification confidence threshold is not configured for Google Cloud Vision engine'
            )
        return self.config.image_classification_confidence

    def _face_detection_threshold(self) -> float:
        if not self.config or self.config.face_detection_confidence is None:
            raise TJBotError('Face detection confidence threshold is not configured for Google Cloud Vision engine')
        return self.config.face_detection_confidence

    async def detect_objects(self, image: ImageInput) -> List[ObjectDetectionResult]:
        self._ensure_client()
        threshold = self._object_detection_threshold()

        source = google_vision.Image(content=self._read_image(image))

        try:
            response = self.client.object_localization(image=source)
            if response.error.message:
                raise TJBotError(f'Google Cloud Vision API error during object detection: {response.error.message}')

            output: List[ObjectDetectionResult] = []
            for obj in response.localized_object_annotations:
                score = float(obj.score or 0.0)
                if score < threshold:
                    continue

                vertices = obj.bounding_poly.normalized_vertices
                if len(vertices) < 3:
                    continue

                x = float(vertices[0].x or 0.0)
                y = float(vertices[0].y or 0.0)
                w = float((vertices[2].x or 0.0) - x)
                h = float((vertices[2].y or 0.0) - y)

                output.append(
                    {
                        'label': obj.name or 'unknown',
                        'confidence': score,
                        'bbox': (x, y, w, h),
                    }
                )

            output.sort(key=lambda item: item['confidence'], reverse=True)
            return output
        except Exception as error:
            if isinstance(error, TJBotError):
                raise
            raise TJBotError(f'Google Cloud Vision API error during object detection: {error}')

    async def classify_image(self, image: ImageInput) -> List[ImageClassificationResult]:
        self._ensure_client()
        threshold = self._classification_threshold()

        source = google_vision.Image(content=self._read_image(image))

        try:
            response = self.client.label_detection(image=source)
            if response.error.message:
                raise TJBotError(f'Google Cloud Vision API error during classification: {response.error.message}')

            output = [
                {
                    'label': label.description or 'unknown',
                    'confidence': float(label.score or 0.0),
                }
                for label in response.label_annotations
                if float(label.score or 0.0) >= threshold
            ]
            output.sort(key=lambda item: item['confidence'], reverse=True)
            return output
        except Exception as error:
            if isinstance(error, TJBotError):
                raise
            raise TJBotError(f'Google Cloud Vision API error during classification: {error}')

    async def detect_faces(self, image: ImageInput) -> FaceDetectionResult:
        self._ensure_client()
        threshold = self._face_detection_threshold()

        source = google_vision.Image(content=self._read_image(image))

        try:
            response = self.client.face_detection(image=source)
            if response.error.message:
                raise TJBotError(f'Google Cloud Vision API error during face detection: {response.error.message}')

            metadata = []
            for face in response.face_annotations:
                confidence = float(face.detection_confidence or 0.0)
                if confidence < threshold:
                    continue

                vertices = face.bounding_poly.vertices
                min_x = min((v.x or 0) for v in vertices) if vertices else 0
                min_y = min((v.y or 0) for v in vertices) if vertices else 0
                max_x = max((v.x or 0) for v in vertices) if vertices else 0
                max_y = max((v.y or 0) for v in vertices) if vertices else 0

                landmarks = [
                    {
                        'x': float(landmark.position.x or 0.0),
                        'y': float(landmark.position.y or 0.0),
                        'type': str(landmark.type),
                    }
                    for landmark in face.landmarks
                ]

                metadata.append(
                    {
                        'boundingBox': (float(min_x), float(min_y), float(max_x - min_x), float(max_y - min_y)),
                        'confidence': confidence,
                        'landmarks': landmarks,
                        'headPose': {
                            'roll': float(face.roll_angle or 0.0),
                            'yaw': float(face.pan_angle or 0.0),
                            'pitch': float(face.tilt_angle or 0.0),
                        },
                    }
                )

            return {
                'isFaceDetected': len(metadata) > 0,
                'metadata': metadata,
            }
        except Exception as error:
            if isinstance(error, TJBotError):
                raise
            raise TJBotError(f'Google Cloud Vision API error during face detection: {error}')

    async def describe_image(self, image: ImageInput) -> ImageDescriptionResult:
        _ = image
        raise TJBotError('Image description is only available with Azure Vision backend. Configure see.backend.type to "azure-vision".')
