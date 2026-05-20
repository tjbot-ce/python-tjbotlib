import importlib
import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Optional


def _find_onnxruntime_capi_dir() -> Optional[Path]:
    """Return the onnxruntime capi/ directory from the installed wheel, or None."""
    spec = importlib.util.find_spec('onnxruntime')
    if spec is None or spec.origin is None:
        return None
    capi_dir = Path(spec.origin).resolve().parent / 'capi'
    return capi_dir if capi_dir.is_dir() else None


def _find_sherpa_onnx_extension() -> Optional[Path]:
    """Return the path to the sherpa_onnx native extension .so, or None."""
    spec = importlib.util.find_spec('sherpa_onnx')
    if spec is None or spec.submodule_search_locations is None:
        return None
    for search_path in spec.submodule_search_locations:
        lib_dir = Path(search_path) / 'lib'
        if lib_dir.is_dir():
            candidates = list(lib_dir.glob('_sherpa_onnx*.so'))
            if candidates:
                return candidates[0]
    return None


def _extension_rpath_includes_ort(ext: Path) -> bool:
    """Return True if the extension's RPATH already includes onnxruntime/capi."""
    try:
        result = subprocess.run(
            ['readelf', '-d', str(ext)],
            capture_output=True, text=True, check=True,
        )
        return 'onnxruntime/capi' in result.stdout
    except Exception:
        return False


def _apply_ort_rpath_fix(ext: Path, capi_dir: Path) -> None:
    """
    Patch the sherpa_onnx native extension so that it finds libonnxruntime.so
    via DT_RPATH rather than relying on LD_LIBRARY_PATH.

    Two steps:
    1. Create (or refresh) an unversioned ``libonnxruntime.so`` symlink in the
       onnxruntime capi directory pointing at the versioned file.
    2. Add ``$ORIGIN/../../onnxruntime/capi`` to the extension's DT_RPATH so
       the dynamic linker finds that symlink before consulting LD_LIBRARY_PATH.
    """
    # Step 1: symlink libonnxruntime.so → libonnxruntime.so.X.Y.Z
    candidates = sorted(capi_dir.glob('libonnxruntime.so.*'))
    if not candidates:
        return
    versioned = candidates[-1]
    symlink = capi_dir / 'libonnxruntime.so'
    if not symlink.exists() or (symlink.is_symlink() and symlink.resolve() != versioned.resolve()):
        symlink.unlink(missing_ok=True)
        symlink.symlink_to(versioned.name)

    # Step 2: inject onnxruntime/capi into RPATH via patchelf (--force-rpath keeps DT_RPATH)
    # $ORIGIN for the extension is sherpa_onnx/lib/, so ../../onnxruntime/capi is correct.
    rpath_entry = '$ORIGIN/../../onnxruntime/capi'
    try:
        result = subprocess.run(
            ['readelf', '-d', str(ext)],
            capture_output=True, text=True, check=True,
        )
        existing_rpath = ''
        for line in result.stdout.splitlines():
            if 'RPATH' in line or 'RUNPATH' in line:
                start = line.find('[')
                end = line.find(']')
                if start != -1 and end != -1:
                    existing_rpath = line[start + 1:end]
                    break

        new_rpath = existing_rpath + ':' + rpath_entry if existing_rpath else rpath_entry
        subprocess.run(
            ['patchelf', '--set-rpath', new_rpath, '--force-rpath', str(ext)],
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def load_sherpa_onnx_module() -> ModuleType:
    """
    Import and return the sherpa_onnx module.

    On first call (or when the venv is freshly created), this automatically
    patches the sherpa_onnx native extension to find the correct
    libonnxruntime.so via DT_RPATH, bypassing any conflicting
    LD_LIBRARY_PATH entries set by other tools (e.g. the Node.js sherpa-onnx
    setup).  The patch is idempotent and survives across process restarts.
    """
    ext = _find_sherpa_onnx_extension()
    if ext is not None and not _extension_rpath_includes_ort(ext):
        capi_dir = _find_onnxruntime_capi_dir()
        if capi_dir is not None:
            _apply_ort_rpath_fix(ext, capi_dir)

    return importlib.import_module('sherpa_onnx')
