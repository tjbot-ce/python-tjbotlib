import ctypes
import importlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Optional


def _find_sherpa_bundled_lib_dir() -> Optional[Path]:
    """Return the sherpa_onnx/lib/ directory inside the installed wheel, or None."""
    spec = importlib.util.find_spec("sherpa_onnx")
    if spec is None or spec.submodule_search_locations is None:
        return None
    for search_path in spec.submodule_search_locations:
        lib_dir = Path(search_path) / "lib"
        if lib_dir.is_dir():
            return lib_dir
    return None


def _preload_sherpa_bundled_libs(lib_dir: Path) -> None:
    """
    Preload libonnxruntime.so and libsherpa-onnx-c-api.so from the wheel's own
    lib/ directory using ctypes.  Because dlopen() caches by resolved path, any
    subsequent dlopen() call for the same library name (from LD_LIBRARY_PATH or
    RUNPATH) will find the already-loaded handle and reuse it — ensuring the
    Python extension always uses its own bundled versions rather than the Node
    sherpa-onnx copies in LD_LIBRARY_PATH.
    """
    # Load order matters: onnxruntime first (it has no sherpa deps), then the
    # sherpa C API (which depends on onnxruntime).
    for pattern in ("libonnxruntime.so*", "libsherpa-onnx-c-api.so*"):
        for lib_path in sorted(lib_dir.glob(pattern)):
            try:
                ctypes.cdll.LoadLibrary(str(lib_path))
                break  # load only the first match per pattern
            except OSError:
                continue


def load_sherpa_onnx_module() -> ModuleType:
    """
    Import and return the sherpa_onnx module, ensuring it uses the libs bundled
    with the Python wheel rather than any conflicting copies in LD_LIBRARY_PATH
    (e.g. the Node sherpa-onnx-linux-arm64 libs set by the TJBot setup script).
    """
    lib_dir = _find_sherpa_bundled_lib_dir()
    if lib_dir is not None:
        _preload_sherpa_bundled_libs(lib_dir)

    return importlib.import_module("sherpa_onnx")
