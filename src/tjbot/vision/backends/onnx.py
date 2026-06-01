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

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...config.config_types import SeeBackendLocalConfig
from ...utils.errors import TJBotError
from ...utils import ModelRegistry
from ..vision_engine import (
    FaceDetectionResult,
    ImageClassificationResult,
    ImageDescriptionResult,
    ImageInput,
    ObjectDetectionResult,
    VisionEngine,
)

np: Any = None
try:
    import numpy as np  # type: ignore[assignment,no-redef]
except ImportError:
    pass

ort: Any = None
try:
    import onnxruntime as ort  # type: ignore[assignment,no-redef]
except ImportError:
    pass

Image: Any = None
try:
    from PIL import Image  # type: ignore[assignment,no-redef]
except ImportError:
    pass


@dataclass
class LoadedModel:
    session: Any
    labels: List[str]
    input_shape: List[int]
    kind: str


class ONNXVisionEngine(VisionEngine):
    def __init__(self, config: Optional[SeeBackendLocalConfig] = None):
        super().__init__(config)
        self.manager = ModelRegistry.get_instance()
        self.models: Dict[str, LoadedModel] = {}

    def initialize(self) -> None:
        if ort is None or np is None or Image is None:
            raise TJBotError(
                "Local ONNX backend requires onnxruntime, numpy, and Pillow to be installed."
            )

        if not self.config:
            raise TJBotError("ONNX vision engine requires local backend configuration.")

        if not self.config.object_detection_model:
            raise TJBotError(
                "ONNX vision engine config is missing required parameter: objectDetectionModel"
            )

        if not self.config.image_classification_model:
            raise TJBotError(
                "ONNX vision engine config is missing required parameter: imageClassificationModel"
            )

        if not self.config.face_detection_model:
            raise TJBotError(
                "ONNX vision engine config is missing required parameter: faceDetectionModel"
            )

        self._load_model(self.config.object_detection_model)
        self._load_model(self.config.image_classification_model)
        self._load_model(self.config.face_detection_model)

    def _load_model(self, model_name: str) -> None:
        if model_name in self.models:
            return

        metadata = self.manager.load_model(model_name)
        model_dir = (
            self.manager.get_model_cache_dir_for_type(metadata.type) / metadata.folder
        )

        onnx_file = next(
            (name for name in metadata.required if name.endswith(".onnx")), None
        )
        if not onnx_file:
            raise TJBotError(
                f"No ONNX file found in model requirements for: {model_name}"
            )

        model_path = model_dir / onnx_file
        session = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )

        labels = self._load_labels(model_dir, metadata.kind)

        input_shape = metadata.inputShape or [1, 3, 640, 640]
        self.models[model_name] = LoadedModel(
            session=session,
            labels=labels,
            input_shape=input_shape,
            kind=metadata.kind or "",
        )

    def _load_labels(self, model_dir: Path, kind: Optional[str]) -> List[str]:
        if kind == "face-detection":
            return []

        label_file = None
        if kind == "detection":
            for name in ["classes.txt", "coco.yaml", "coco.names"]:
                candidate = model_dir / name
                if candidate.exists():
                    label_file = candidate
                    break
        elif kind == "classification":
            for name in ["imagenet_classes.txt", "labels.txt", "classes.txt"]:
                candidate = model_dir / name
                if candidate.exists():
                    label_file = candidate
                    break

        if label_file is None:
            return []

        content = label_file.read_text(encoding="utf-8")
        if label_file.suffix == ".yaml" and kind == "detection":
            # Simple YAML names extraction compatibility for common coco yaml format.
            if "names:" in content:
                names_section = content.split("names:", 1)[1]
                if "[" in names_section and "]" in names_section:
                    inline = names_section[
                        names_section.index("[") + 1 : names_section.index("]")
                    ]
                    return [
                        entry.strip().strip("'\"")
                        for entry in inline.split(",")
                        if entry.strip()
                    ]

            labels = []
            for line in names_section.splitlines():
                line = line.strip()
                if ":" in line:
                    _, _, value = line.partition(":")
                    value = value.strip().strip("'\"")
                    if value:
                        labels.append(value)
            if labels:
                return labels

        labels = [line.strip() for line in content.splitlines() if line.strip()]
        if labels and ":" in labels[0]:
            normalized = []
            for line in labels:
                if ":" in line:
                    _, _, value = line.partition(":")
                    normalized.append(value.strip())
                else:
                    normalized.append(line)
            return normalized

        return labels

    def _ensure_initialized(self):
        if not self.models:
            raise TJBotError(
                "ONNX vision engine not initialized. Call initialize() first."
            )

    def _get_model(self, model_name: str) -> LoadedModel:
        model = self.models.get(model_name)
        if not model:
            self._load_model(model_name)
            model = self.models.get(model_name)
        if not model:
            raise TJBotError(f"Failed to load model: {model_name}")
        return model

    def _read_image(self, image: ImageInput) -> Any:
        if isinstance(image, str):
            return Image.open(image).convert("RGB")
        return Image.open(__import__("io").BytesIO(image)).convert("RGB")

    def _preprocess_image(self, image: ImageInput, size: Tuple[int, int]) -> Any:
        img = self._read_image(image)
        img = img.resize(size)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        chw = np.transpose(arr, (2, 0, 1))
        return np.expand_dims(chw, axis=0).astype(np.float32)

    def _preprocess_face_image(self, image: ImageInput, size: Tuple[int, int]) -> Any:
        img = self._read_image(image)
        img = img.resize(size)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        # Convert RGB -> BGR then normalize to [-1, 1]
        arr = arr[:, :, ::-1]
        arr = arr * 2.0 - 1.0
        chw = np.transpose(arr, (2, 0, 1))
        return np.expand_dims(chw, axis=0).astype(np.float32)

    def _sigmoid(self, value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    def _softmax(self, values) -> Any:
        values = np.asarray(values, dtype=np.float32)
        shifted = values - np.max(values)
        exps = np.exp(shifted)
        denom = np.sum(exps)
        return exps / denom if denom else exps

    def _calculate_iou(
        self,
        bbox1: Tuple[float, float, float, float],
        bbox2: Tuple[float, float, float, float],
    ) -> float:
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        box1_xmax = x1 + w1
        box1_ymax = y1 + h1
        box2_xmax = x2 + w2
        box2_ymax = y2 + h2

        inter_xmin = max(x1, x2)
        inter_ymin = max(y1, y2)
        inter_xmax = min(box1_xmax, box2_xmax)
        inter_ymax = min(box1_ymax, box2_ymax)

        inter_w = max(0.0, inter_xmax - inter_xmin)
        inter_h = max(0.0, inter_ymax - inter_ymin)
        inter = inter_w * inter_h

        union = (w1 * h1) + (w2 * h2) - inter
        return inter / union if union > 0 else 0.0

    def _non_max_suppression(
        self, detections: List[ObjectDetectionResult], iou_threshold: float = 0.5
    ) -> List[ObjectDetectionResult]:
        if not detections:
            return []

        sorted_detections = sorted(
            detections, key=lambda d: d["confidence"], reverse=True
        )
        kept: List[ObjectDetectionResult] = []
        for detection in sorted_detections:
            overlaps = False
            for existing in kept:
                iou = self._calculate_iou(detection["bbox"], existing["bbox"])
                if iou > iou_threshold:
                    overlaps = True
                    break
            if not overlaps:
                kept.append(detection)
        return kept

    def _postprocess_ssd_mobilenet_v2(
        self, outputs: Dict[str, Any], labels: List[str], confidence_threshold: float
    ) -> List[ObjectDetectionResult]:
        box_scales = {"x": 10.0, "y": 10.0, "w": 5.0, "h": 5.0}
        feature_map_shapes = [(19, 19), (10, 10), (5, 5), (3, 3), (2, 2), (1, 1)]

        anchors_by_layer = self._generate_ssd_mobilenet_v2_anchors(feature_map_shapes)
        detections: List[ObjectDetectionResult] = []

        for layer, (feat_h, feat_w) in enumerate(feature_map_shapes):
            box_tensor = outputs.get(
                f"BoxPredictor_{layer}/BoxEncodingPredictor/BiasAdd:0"
            )
            class_tensor = outputs.get(f"BoxPredictor_{layer}/ClassPredictor/BiasAdd:0")
            if box_tensor is None or class_tensor is None:
                continue

            box_data = np.asarray(box_tensor).reshape(np.asarray(box_tensor).shape)
            class_data = np.asarray(class_tensor).reshape(
                np.asarray(class_tensor).shape
            )

            _, box_channels, h, w = box_data.shape
            _, class_channels, _, _ = class_data.shape

            num_anchors_per_cell = box_channels // 4
            num_classes_with_background = class_channels // num_anchors_per_cell

            for y in range(h):
                for x in range(w):
                    for a in range(num_anchors_per_cell):
                        anchor_idx = (y * w + x) * num_anchors_per_cell + a
                        anchor = anchors_by_layer[layer][anchor_idx]

                        class_logits = np.zeros(
                            (num_classes_with_background,), dtype=np.float32
                        )
                        for c in range(num_classes_with_background):
                            class_channel = a * num_classes_with_background + c
                            class_logits[c] = class_data[0, class_channel, y, x]

                        probs = self._softmax(class_logits)

                        best_class = 0
                        best_score = 0.0
                        for c in range(1, len(probs)):
                            if probs[c] > best_score:
                                best_score = float(probs[c])
                                best_class = c

                        if best_score < confidence_threshold:
                            continue

                        ty = float(box_data[0, a * 4 + 0, y, x])
                        tx = float(box_data[0, a * 4 + 1, y, x])
                        th = float(box_data[0, a * 4 + 2, y, x])
                        tw = float(box_data[0, a * 4 + 3, y, x])

                        y_center = (ty / box_scales["y"]) * anchor["h"] + anchor["cy"]
                        x_center = (tx / box_scales["x"]) * anchor["w"] + anchor["cx"]
                        box_h = math.exp(th / box_scales["h"]) * anchor["h"]
                        box_w = math.exp(tw / box_scales["w"]) * anchor["w"]

                        x_min = max(0.0, min(1.0, x_center - box_w / 2.0))
                        y_min = max(0.0, min(1.0, y_center - box_h / 2.0))
                        x_max = max(0.0, min(1.0, x_center + box_w / 2.0))
                        y_max = max(0.0, min(1.0, y_center + box_h / 2.0))

                        width = x_max - x_min
                        height = y_max - y_min
                        if width <= 0.0 or height <= 0.0:
                            continue

                        label_idx = best_class - 1
                        label = (
                            labels[label_idx]
                            if 0 <= label_idx < len(labels)
                            else f"class{label_idx}"
                        )
                        detections.append(
                            {
                                "label": label,
                                "confidence": best_score,
                                "bbox": (x_min, y_min, width, height),
                            }
                        )

        return self._non_max_suppression(detections)

    def _generate_ssd_mobilenet_v2_anchors(
        self, feature_map_shapes: List[Tuple[int, int]]
    ) -> List[Any]:
        min_scale = 0.2
        max_scale = 0.95
        aspect_ratios = [1.0, 2.0, 0.5, 3.0, 1.0 / 3.0]
        anchors_by_layer = []

        def scale_for_layer(layer: int) -> float:
            if len(feature_map_shapes) == 1:
                return (min_scale + max_scale) * 0.5
            return min_scale + ((max_scale - min_scale) * layer) / (
                len(feature_map_shapes) - 1
            )

        for layer, (feat_h, feat_w) in enumerate(feature_map_shapes):
            scale = scale_for_layer(layer)
            next_scale = (
                1.0
                if layer == len(feature_map_shapes) - 1
                else scale_for_layer(layer + 1)
            )
            layer_anchors = []

            anchor_sizes = []
            if layer == 0:
                anchor_sizes.append({"w": 0.1, "h": 0.1})
                anchor_sizes.append(
                    {"w": scale * math.sqrt(2.0), "h": scale / math.sqrt(2.0)}
                )
                anchor_sizes.append(
                    {"w": scale / math.sqrt(2.0), "h": scale * math.sqrt(2.0)}
                )
            else:
                for ratio in aspect_ratios:
                    ratio_sqrt = math.sqrt(ratio)
                    anchor_sizes.append(
                        {"w": scale * ratio_sqrt, "h": scale / ratio_sqrt}
                    )
                interpolated = math.sqrt(scale * next_scale)
                anchor_sizes.append({"w": interpolated, "h": interpolated})

            for y in range(feat_h):
                for x in range(feat_w):
                    cy = (y + 0.5) / feat_h
                    cx = (x + 0.5) / feat_w
                    for size in anchor_sizes:
                        layer_anchors.append(
                            {"cx": cx, "cy": cy, "w": size["w"], "h": size["h"]}
                        )

            anchors_by_layer.append(layer_anchors)

        return anchors_by_layer

    def _postprocess_detection(
        self,
        outputs: Dict[str, Any],
        labels: List[str],
        output_names: List[str],
        threshold: float,
    ) -> List[ObjectDetectionResult]:
        if any("BoxPredictor_" in name for name in output_names):
            return self._postprocess_ssd_mobilenet_v2(outputs, labels, threshold)

        output_name = output_names[0]
        output_data = np.asarray(outputs[output_name]).flatten()
        num_classes = len(labels) or 80
        values_per_detection = 5 + num_classes
        detections: List[ObjectDetectionResult] = []

        for i in range(0, len(output_data), values_per_detection):
            confidence = self._sigmoid(float(output_data[i + 4]))
            if confidence < threshold:
                continue

            max_class_score = 0.0
            max_class_idx = 0
            for j in range(num_classes):
                score = self._sigmoid(float(output_data[i + 5 + j]))
                if score > max_class_score:
                    max_class_score = score
                    max_class_idx = j

            label = (
                labels[max_class_idx]
                if max_class_idx < len(labels)
                else f"class{max_class_idx}"
            )
            x = float(output_data[i])
            y = float(output_data[i + 1])
            w = float(output_data[i + 2])
            h = float(output_data[i + 3])
            detections.append(
                {"label": label, "confidence": max_class_score, "bbox": (x, y, w, h)}
            )

        return self._non_max_suppression(detections)

    def _postprocess_classification(
        self,
        outputs: Dict[str, Any],
        labels: List[str],
        threshold: float,
        output_names: List[str],
    ):
        logits = np.asarray(outputs[output_names[0]]).flatten()
        scores = self._softmax(logits)
        results: List[ImageClassificationResult] = []

        for i, score in enumerate(scores):
            confidence = float(score)
            if confidence < threshold:
                continue
            label = labels[i] if i < len(labels) else f"class{i}"
            results.append({"label": label, "confidence": confidence})

        results.sort(key=lambda item: item["confidence"], reverse=True)
        return results

    def _compute_iou(self, box1, box2) -> float:
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2

        x1_max = x1 + w1
        y1_max = y1 + h1
        x2_max = x2 + w2
        y2_max = y2 + h2

        inter_xmin = max(x1, x2)
        inter_ymin = max(y1, y2)
        inter_xmax = min(x1_max, x2_max)
        inter_ymax = min(y1_max, y2_max)

        if inter_xmin >= inter_xmax or inter_ymin >= inter_ymax:
            return 0.0

        inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)
        union_area = (w1 * h1) + (w2 * h2) - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    def _apply_face_nms(
        self, faces: List[Any], iou_threshold: float = 0.5
    ) -> List[Any]:
        if not faces:
            return []

        sorted_faces = sorted(faces, key=lambda item: item["confidence"], reverse=True)
        kept = []
        suppressed = [False] * len(sorted_faces)

        for i in range(len(sorted_faces)):
            if suppressed[i]:
                continue
            kept.append(sorted_faces[i])
            for j in range(i + 1, len(sorted_faces)):
                if suppressed[j]:
                    continue
                iou = self._compute_iou(
                    sorted_faces[i]["boundingBox"], sorted_faces[j]["boundingBox"]
                )
                if iou > iou_threshold:
                    suppressed[j] = True

        return kept

    def _postprocess_scrfd_face_detection(
        self,
        outputs: Dict[str, Any],
        threshold: float,
        model_input_size: Tuple[int, int],
    ) -> FaceDetectionResult:
        model_width, model_height = model_input_size
        faces = []

        scales = [
            {"stride": 8, "scoreKey": "446", "bboxKey": "449", "kpsKey": "452"},
            {"stride": 16, "scoreKey": "466", "bboxKey": "469", "kpsKey": "472"},
            {"stride": 32, "scoreKey": "486", "bboxKey": "489", "kpsKey": "492"},
        ]

        for scale in scales:
            score_tensor = outputs.get(scale["scoreKey"])
            bbox_tensor = outputs.get(scale["bboxKey"])
            kps_tensor = outputs.get(scale["kpsKey"])

            if score_tensor is None or bbox_tensor is None:
                continue

            scores = np.asarray(score_tensor).flatten()
            bboxes = np.asarray(bbox_tensor).flatten()
            kps = np.asarray(kps_tensor).flatten() if kps_tensor is not None else None

            grid_size = int(model_width / scale["stride"])
            num_anchors = 2

            for i, confidence in enumerate(scores):
                confidence = float(confidence)
                if confidence < threshold:
                    continue

                anchor_index = i // num_anchors
                grid_y = anchor_index // grid_size
                grid_x = anchor_index % grid_size
                anchor_x = (grid_x + 0.5) * scale["stride"]
                anchor_y = (grid_y + 0.5) * scale["stride"]

                left = float(bboxes[i * 4 + 0]) * scale["stride"]
                top = float(bboxes[i * 4 + 1]) * scale["stride"]
                right = float(bboxes[i * 4 + 2]) * scale["stride"]
                bottom = float(bboxes[i * 4 + 3]) * scale["stride"]

                x1 = max(0.0, anchor_x - left)
                y1 = max(0.0, anchor_y - top)
                x2 = min(float(model_width), anchor_x + right)
                y2 = min(float(model_height), anchor_y + bottom)
                if x2 <= x1 or y2 <= y1:
                    continue

                box_w = x2 - x1
                box_h = y2 - y1

                landmarks = []
                if kps is not None and len(kps) >= i * 10 + 10:
                    landmark_types = [
                        "eye-left",
                        "eye-right",
                        "nose",
                        "mouth-left",
                        "mouth-right",
                    ]
                    for j in range(5):
                        kx = (
                            float(kps[i * 10 + j * 2]) * scale["stride"] + anchor_x
                        ) / model_width
                        ky = (
                            float(kps[i * 10 + j * 2 + 1]) * scale["stride"] + anchor_y
                        ) / model_height
                        landmarks.append(
                            {
                                "x": min(1.0, max(0.0, kx)),
                                "y": min(1.0, max(0.0, ky)),
                                "type": landmark_types[j],
                            }
                        )

                faces.append(
                    {
                        "boundingBox": (
                            x1 / model_width,
                            y1 / model_height,
                            box_w / model_width,
                            box_h / model_height,
                        ),
                        "confidence": confidence,
                        "landmarks": landmarks,
                    }
                )

        return self._apply_face_nms(faces, 0.45)

    def _postprocess_face_detection(
        self,
        outputs: Dict[str, Any],
        threshold: float,
        model_input_size: Tuple[int, int],
    ):
        return self._postprocess_scrfd_face_detection(
            outputs, threshold, model_input_size
        )

    def _get_object_detection_threshold(self) -> float:
        if not self.config or self.config.object_detection_confidence is None:
            raise TJBotError(
                "Object detection confidence threshold is not configured for ONNX vision engine"
            )
        return float(self.config.object_detection_confidence)

    def _get_image_classification_threshold(self) -> float:
        if not self.config or self.config.image_classification_confidence is None:
            raise TJBotError(
                "Image classification confidence threshold is not configured for ONNX vision engine"
            )
        return float(self.config.image_classification_confidence)

    def _get_face_detection_threshold(self) -> float:
        if not self.config or self.config.face_detection_confidence is None:
            raise TJBotError(
                "Face detection confidence threshold is not configured for ONNX vision engine"
            )
        return float(self.config.face_detection_confidence)

    def detect_objects(self, image: ImageInput) -> List[ObjectDetectionResult]:
        self._ensure_initialized()

        if not self.config or not self.config.object_detection_model:
            raise TJBotError(
                "Object detection model is not configured for ONNX vision engine"
            )

        model = self._get_model(self.config.object_detection_model)
        _, _, height, width = model.input_shape
        input_tensor = self._preprocess_image(image, (width, height))

        input_name = model.session.get_inputs()[0].name
        outputs = model.session.run(None, {input_name: input_tensor})
        output_names = [output.name for output in model.session.get_outputs()]
        output_map = {name: tensor for name, tensor in zip(output_names, outputs)}

        threshold = self._get_object_detection_threshold()
        return self._postprocess_detection(
            output_map, model.labels, output_names, threshold
        )

    def classify_image(self, image: ImageInput) -> List[ImageClassificationResult]:
        self._ensure_initialized()

        if not self.config or not self.config.image_classification_model:
            raise TJBotError(
                "Image classification model is not configured for ONNX vision engine"
            )

        model = self._get_model(self.config.image_classification_model)
        _, _, height, width = model.input_shape
        input_tensor = self._preprocess_image(image, (width, height))

        input_name = model.session.get_inputs()[0].name
        outputs = model.session.run(None, {input_name: input_tensor})
        output_names = [output.name for output in model.session.get_outputs()]
        output_map = {name: tensor for name, tensor in zip(output_names, outputs)}

        threshold = self._get_image_classification_threshold()
        return self._postprocess_classification(
            output_map, model.labels, threshold, output_names
        )

    def detect_faces(self, image: ImageInput) -> FaceDetectionResult:
        self._ensure_initialized()

        if not self.config or not self.config.face_detection_model:
            raise TJBotError(
                "Face detection model is not configured for ONNX vision engine"
            )

        model = self._get_model(self.config.face_detection_model)
        _, _, height, width = model.input_shape
        input_tensor = self._preprocess_face_image(image, (width, height))

        input_name = model.session.get_inputs()[0].name
        outputs = model.session.run(None, {input_name: input_tensor})
        output_names = [output.name for output in model.session.get_outputs()]
        output_map = {name: tensor for name, tensor in zip(output_names, outputs)}

        threshold = self._get_face_detection_threshold()
        metadata = self._postprocess_face_detection(
            output_map, threshold, (width, height)
        )
        return {"isFaceDetected": len(metadata) > 0, "metadata": metadata}

    def describe_image(self, image: ImageInput) -> ImageDescriptionResult:
        _ = image
        raise TJBotError(
            "Image description is only supported by the Azure vision backend."
        )
