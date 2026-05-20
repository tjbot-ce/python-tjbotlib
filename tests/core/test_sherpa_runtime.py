import types
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from tjbot.utils.sherpa_runtime import (
    _apply_ort_rpath_fix,
    _extension_rpath_includes_ort,
    load_sherpa_onnx_module,
)


def test_load_sherpa_module_returns_imported_module(monkeypatch):
    fake_module = types.ModuleType('sherpa_onnx')
    monkeypatch.setattr('importlib.import_module', lambda name: fake_module)
    # Pretend extension already patched so no subprocess calls happen
    monkeypatch.setattr('tjbot.utils.sherpa_runtime._find_sherpa_onnx_extension', lambda: None)

    loaded = load_sherpa_onnx_module()
    assert loaded is fake_module


def test_load_sherpa_module_applies_fix_when_rpath_missing(monkeypatch, tmp_path):
    """load_sherpa_onnx_module() calls _apply_ort_rpath_fix when RPATH is missing."""
    fake_module = types.ModuleType('sherpa_onnx')
    fake_ext = tmp_path / '_sherpa_onnx.cpython-311.so'
    fake_ext.write_bytes(b'')
    fake_capi = tmp_path / 'capi'
    fake_capi.mkdir()

    monkeypatch.setattr('tjbot.utils.sherpa_runtime._find_sherpa_onnx_extension', lambda: fake_ext)
    monkeypatch.setattr('tjbot.utils.sherpa_runtime._extension_rpath_includes_ort', lambda ext: False)
    monkeypatch.setattr('tjbot.utils.sherpa_runtime._find_onnxruntime_capi_dir', lambda: fake_capi)
    apply_calls: list = []
    monkeypatch.setattr(
        'tjbot.utils.sherpa_runtime._apply_ort_rpath_fix',
        lambda ext, capi: apply_calls.append((ext, capi)),
    )
    monkeypatch.setattr('importlib.import_module', lambda name: fake_module)

    load_sherpa_onnx_module()
    assert apply_calls == [(fake_ext, fake_capi)]


def test_load_sherpa_module_skips_fix_when_rpath_present(monkeypatch, tmp_path):
    """load_sherpa_onnx_module() skips _apply_ort_rpath_fix when RPATH already set."""
    fake_module = types.ModuleType('sherpa_onnx')
    fake_ext = tmp_path / '_sherpa_onnx.cpython-311.so'
    fake_ext.write_bytes(b'')

    monkeypatch.setattr('tjbot.utils.sherpa_runtime._find_sherpa_onnx_extension', lambda: fake_ext)
    monkeypatch.setattr('tjbot.utils.sherpa_runtime._extension_rpath_includes_ort', lambda ext: True)
    apply_calls: list = []
    monkeypatch.setattr(
        'tjbot.utils.sherpa_runtime._apply_ort_rpath_fix',
        lambda ext, capi: apply_calls.append((ext, capi)),
    )
    monkeypatch.setattr('importlib.import_module', lambda name: fake_module)

    load_sherpa_onnx_module()
    assert apply_calls == []


def test_apply_ort_rpath_fix_creates_symlink(tmp_path):
    """_apply_ort_rpath_fix creates libonnxruntime.so → versioned file symlink."""
    capi_dir = tmp_path / 'onnxruntime' / 'capi'
    capi_dir.mkdir(parents=True)
    versioned = capi_dir / 'libonnxruntime.so.1.24.4'
    versioned.write_bytes(b'')
    ext = tmp_path / '_sherpa_onnx.cpython-311.so'
    ext.write_bytes(b'')

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(stdout='(RPATH) [$ORIGIN]', returncode=0)
        _apply_ort_rpath_fix(ext, capi_dir)

    symlink = capi_dir / 'libonnxruntime.so'
    assert symlink.is_symlink()
    assert symlink.readlink() == Path('libonnxruntime.so.1.24.4')


def test_extension_rpath_includes_ort_returns_true_when_present(tmp_path):
    ext = tmp_path / 'fake.so'
    ext.write_bytes(b'')
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            stdout='(RPATH) [$ORIGIN:$ORIGIN/../../onnxruntime/capi]',
            returncode=0,
        )
        assert _extension_rpath_includes_ort(ext) is True


def test_extension_rpath_includes_ort_returns_false_when_absent(tmp_path):
    ext = tmp_path / 'fake.so'
    ext.write_bytes(b'')
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            stdout='(RPATH) [$ORIGIN:$ORIGIN/../../sherpa_onnx.libs]',
            returncode=0,
        )
        assert _extension_rpath_includes_ort(ext) is False
