#!/usr/bin/env python3

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

"""
Interactive TJBot Vision Test

This test mirrors the Node live vision harness: it prompts for backend/task,
initializes TJBot, captures an image, runs the selected vision operation, and
optionally writes an annotated image for detection/face results.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))

from tjbot import TJBot
from tjbot.utils import ModelRegistry

try:
    from .utils import (
        format_title,
        format_section,
        select_option,
        is_command_available,
    )
except ImportError:
    from utils import (
        format_title,
        format_section,
        select_option,
        is_command_available,
    )

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - live script only
    Image = None
    ImageDraw = None
    ImageFont = None

BACKENDS = [
    {"id": "local", "label": "Local (ONNX)"},
    {"id": "google-cloud-vision", "label": "Google Cloud Vision"},
    {"id": "azure-vision", "label": "Azure Vision"},
]

VISION_TASKS = ["detectObjects", "classifyImage", "detectFaces", "describeImage"]


def run_test() -> None:
    print(format_title("TJBot Vision Test"))

    if not is_command_available("rpicam-still"):
        print("✗ rpicam-still command not available (required for camera capture)")
        print("\nInstall with:")
        print("  sudo apt-get install rpicam-apps-lite\n")
        sys.exit(1)

    can_annotate = Image is not None
    if not can_annotate:
        print("ℹ️  Pillow not installed; annotation output will be skipped")

    selected_backend = prompt_backend_choice()
    task = prompt_task_choice(selected_backend)
    prompt_backend_specific_options(selected_backend, task)
    see_config = build_see_config(selected_backend)

    backend_label = next(
        (b["label"] for b in BACKENDS if b["id"] == selected_backend), "Unknown"
    )
    print(format_section(f"Initializing TJBot with Vision ({backend_label})"))

    tjbot = TJBot(
        {
            "log": {"level": "info"},
            "hardware": {
                "camera": True,
                "led": False,
                "microphone": False,
                "servo": False,
                "speaker": False,
            },
            "see": see_config,
        }
    )
    print("✓ TJBot initialized")

    img_path = Path("/tmp") / f"tjbot-vision-test-{os.getpid()}.jpg"
    print(format_section("Capturing image and running vision task"))
    print("Capturing image from camera...")
    tjbot.look(str(img_path))
    img_buf = img_path.read_bytes()

    result: Any = None
    if task == "detectObjects":
        result = tjbot.detect_objects(img_buf)
    elif task == "classifyImage":
        result = tjbot.classify_image(img_buf)
    elif task == "detectFaces":
        result = tjbot.detect_faces(img_buf)
    elif task == "describeImage":
        result = tjbot.describe_image(img_buf)

    print("\nResult:")
    print(json.dumps(result, indent=2, default=str))

    if (
        can_annotate
        and task in ("detectObjects", "detectFaces")
        and result
        and isinstance(result, dict)
        and isinstance(result.get("metadata"), list)
    ):
        annotated_path = annotate_image_with_bounding_boxes(img_path, result)
        print(f"\n✓ Original image saved to: {img_path}")
        print(f"✓ Annotated image saved to: {annotated_path}")
    else:
        print(f"\n✓ Test image saved to: {img_path}")

    print("\n✓ Vision test complete")


def prompt_backend_choice() -> str:
    return select_option(
        "Select a Vision backend to test:",
        [{"name": backend["label"], "value": backend["id"]} for backend in BACKENDS],
        default="local",
    )


def prompt_backend_specific_options(selected_backend: str, task: str) -> Dict[str, Any]:
    if selected_backend == "local":
        return prompt_onnx_vision_options(task)
    if selected_backend == "google-cloud-vision":
        print("\nUsing Google Cloud Vision with default credentials")
        return {}
    if selected_backend == "azure-vision":
        print("\nUsing Azure Computer Vision with default credentials")
        return {}
    return {}


def prompt_onnx_vision_options(task: str) -> Dict[str, Any]:
    model_type_map = {
        "detectObjects": "vision.object-recognition",
        "classifyImage": "vision.classification",
        "detectFaces": "vision.face-detection",
    }

    if task == "describeImage":
        return {}

    model_type = model_type_map[task]
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models(model_type, False)
    if not models:
        print(f"\nNo models available for task: {task}")
        return {}

    default_model = models[0]
    downloaded = registry.is_model_downloaded(default_model.key)
    status = "✓ downloaded" if downloaded else "✗ not downloaded"
    print(f"\nUsing model: {default_model.label or default_model.key} {status}")
    return {}


def prompt_task_choice(selected_backend: str) -> str:
    registry = ModelRegistry.get_instance()
    detection_models = registry.lookup_models("vision.object-recognition", False)
    classification_models = registry.lookup_models("vision.classification", False)
    face_detection_models = registry.lookup_models("vision.face-detection", False)
    image_description_models = registry.lookup_models("vision.image-description", False)

    if not detection_models or not classification_models or not face_detection_models:
        raise RuntimeError("Required vision models not found in registry")

    detection_label = detection_models[0].label or detection_models[0].key
    classification_label = (
        classification_models[0].label or classification_models[0].key
    )
    face_detection_label = (
        face_detection_models[0].label or face_detection_models[0].key
    )

    tasks: List[Dict[str, str]] = [
        {
            "name": f"Object detection ({detection_label})"
            if selected_backend == "local"
            else "Object detection",
            "value": "detectObjects",
        },
        {
            "name": f"Image classification ({classification_label})"
            if selected_backend == "local"
            else "Image classification",
            "value": "classifyImage",
        },
    ]

    if selected_backend != "azure-vision":
        tasks.append(
            {
                "name": f"Face detection ({face_detection_label})"
                if selected_backend == "local"
                else "Face detection",
                "value": "detectFaces",
            }
        )

    if selected_backend == "azure-vision" and image_description_models:
        tasks.append({"name": "Image description", "value": "describeImage"})

    return select_option("Choose a vision task:", tasks)


def build_see_config(selected_backend: str) -> Dict[str, Any]:
    base_config: Dict[str, Any] = {
        "backend": {
            "type": selected_backend,
        },
    }

    if selected_backend == "local":
        registry = ModelRegistry.get_instance()
        detection_models = registry.lookup_models("vision.object-recognition", False)
        classification_models = registry.lookup_models("vision.classification", False)
        face_detection_models = registry.lookup_models("vision.face-detection", False)

        local_config: Dict[str, Any] = {}
        if detection_models:
            local_config["objectDetectionModel"] = detection_models[0].key
        if classification_models:
            local_config["imageClassificationModel"] = classification_models[0].key
        if face_detection_models:
            local_config["faceDetectionModel"] = face_detection_models[0].key

        base_config["backend"]["local"] = local_config
    elif selected_backend == "google-cloud-vision":
        base_config["backend"]["google-cloud-vision"] = {}
    elif selected_backend == "azure-vision":
        base_config["backend"]["azure-vision"] = {}

    return base_config


def annotate_image_with_bounding_boxes(img_path: Path, result: Dict[str, Any]) -> str:
    from PIL import Image, ImageDraw

    with Image.open(img_path) as image:
        width, height = image.size
        canvas = image.convert("RGB")
        draw = ImageDraw.Draw(canvas)

        for item in result.get("metadata", []):
            bbox = item.get("boundingBox")
            if not bbox:
                continue

            x, y, w, h = bbox
            x1 = round(x * width)
            y1 = round(y * height)
            x2 = round((x + w) * width)
            y2 = round((y + h) * height)

            confidence = item.get("confidence")
            if confidence is None:
                color = "#00FF00"
            elif confidence < 0.5:
                color = "#FF0000"
            elif confidence < 0.7:
                color = "#FFFF00"
            else:
                color = "#00FF00"

            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

            if confidence is not None:
                draw.text(
                    (x1 + 5, max(0, y1 - 18)), f"{confidence * 100:.1f}%", fill=color
                )

            for landmark in item.get("landmarks", []):
                lx = round(landmark["x"] * width)
                ly = round(landmark["y"] * height)
                draw.ellipse([lx - 3, ly - 3, lx + 3, ly + 3], fill=color)
                if landmark.get("type"):
                    draw.text((lx + 6, ly - 10), landmark["type"], fill=color)

        annotated_path = f"/tmp/tjbot-vision-test-annotated-{os.getpid()}.jpg"
        canvas.save(annotated_path, quality=90)
        return annotated_path


if __name__ == "__main__":
    run_test()
