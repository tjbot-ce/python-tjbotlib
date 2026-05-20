import asyncio
import pytest
from pathlib import Path

from tjbot.utils.errors import TJBotError
from tjbot.vision.backends.azure_vision import AzureVisionEngine
from tjbot.vision.backends.google_cloud_vision import GoogleCloudVisionEngine


def test_google_vision_requires_initialize_before_calls():
    engine = GoogleCloudVisionEngine(None)

    with pytest.raises(TJBotError, match='not initialized'):
        asyncio.run(engine.detect_objects(b'image'))



def test_azure_vision_requires_initialize_before_calls():
    engine = AzureVisionEngine(None)

    with pytest.raises(TJBotError, match='not initialized'):
        asyncio.run(engine.detect_objects(b'image'))



def test_azure_vision_face_detection_reports_unsupported():
    engine = AzureVisionEngine(None)

    with pytest.raises(TJBotError, match='Face detection is not supported'):
        asyncio.run(engine.detect_faces(b'image'))


def test_azure_vision_read_image_returns_stream(tmp_path):
    engine = AzureVisionEngine(None)

    file_path = Path(tmp_path) / 'image.bin'
    file_path.write_bytes(b'abc')

    stream_from_bytes = engine._read_image(b'data')
    stream_from_file = engine._read_image(str(file_path))

    assert hasattr(stream_from_bytes, 'read')
    assert hasattr(stream_from_file, 'read')
    assert stream_from_bytes.read() == b'data'
    assert stream_from_file.read() == b'abc'
