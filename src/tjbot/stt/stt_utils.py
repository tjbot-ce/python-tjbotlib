"""
STT utility functions for mode inference and stream-end handling.
Mirrors node-tjbotlib/src/stt/stt-utils.ts
"""

import re
from typing import Literal, Optional
from ..config.config_types import ListenConfig
from ..utils.errors import TJBotError

STTModelType = Literal["streaming", "offline"]
STTModelFlavor = Literal[
    "streaming-zipformer",
    "streaming-paraformer",
    "offline-whisper",
    "offline-moonshine",
]

_TIMEOUT_LIKE_STREAM_END_PATTERNS = [
    re.compile(r"max duration.*5 minutes.*stream", re.IGNORECASE),
    re.compile(r"maximum stream duration", re.IGNORECASE),
    re.compile(r"stream.*time(?:d)? out", re.IGNORECASE),
    re.compile(r"request.*time(?:d)? out", re.IGNORECASE),
    re.compile(r"session stopped", re.IGNORECASE),
    re.compile(r"inactivity timeout", re.IGNORECASE),
]


def infer_local_model_flavor(
    model_name: Optional[str] = None, model_url: Optional[str] = None
) -> STTModelFlavor:
    """
    Infer sherpa-onnx local model flavor from model name/URL.
    Throws a TJBotError if the flavor cannot be determined.
    """
    name = (model_name or "").lower()
    url = (model_url or "").lower()
    haystack = f"{name} {url}"

    import re

    is_whisper = bool(re.search(r"whisper", haystack))
    is_moonshine = bool(re.search(r"moonshine", haystack))
    is_zipformer = bool(
        re.search(r"zipformer|transducer|streaming-zipformer", haystack)
    )
    is_paraformer = bool(re.search(r"paraformer", haystack))

    if is_whisper:
        return "offline-whisper"
    if is_moonshine:
        return "offline-moonshine"
    if is_zipformer:
        return "streaming-zipformer"
    if is_paraformer:
        return "streaming-paraformer"

    raise TJBotError(
        "Unable to infer STT model type. Provide a sherpa-onnx model name/URL that indicates "
        "whisper, moonshine, zipformer, or paraformer."
    )


def to_model_type(flavor: STTModelFlavor) -> STTModelType:
    return "streaming" if flavor.startswith("streaming") else "offline"


def infer_stt_mode(listen_config: ListenConfig) -> STTModelType:
    """
    Infer whether the configured STT backend operates in 'streaming' or 'offline' mode.
    Streaming backends deliver partial results via callbacks; offline backends return a
    single transcript when the utterance is complete.
    """
    backend = listen_config.backend
    backend_type = backend.type if backend else "local"

    if backend_type == "none":
        # STT is disabled; mode doesn't matter
        return "offline"

    if backend_type == "ibm-watson-stt":
        ibm_cfg = backend.ibm_watson_stt if backend else None
        if ibm_cfg and ibm_cfg.interim_results:
            return "streaming"
        return "offline"

    if backend_type == "google-cloud-stt":
        google_cfg = backend.google_cloud_stt if backend else None
        if google_cfg and google_cfg.interim_results:
            return "streaming"
        return "offline"

    if backend_type == "azure-stt":
        # Azure is single-shot request/response; treat as offline
        return "offline"

    if backend_type == "local":
        local_cfg = backend.local if backend else None
        model_name = local_cfg.model if local_cfg else None
        model_url = local_cfg.model_url if local_cfg else None
        flavor = infer_local_model_flavor(model_name, model_url)
        return to_model_type(flavor)

    raise TJBotError(f"Unknown STT backend type: {backend_type}")


def is_timeout_like_stream_end_reason(reason: Optional[str]) -> bool:
    if not reason:
        return False
    return any(pattern.search(reason) for pattern in _TIMEOUT_LIKE_STREAM_END_PATTERNS)


def resolve_transcript_for_stream_end(
    final_transcript: Optional[str],
    partial_transcript: Optional[str],
    *,
    allow_partial_on_timeout_like_end: bool,
    timeout_like_end: bool,
) -> Optional[str]:
    normalized_final = (final_transcript or "").strip()
    if normalized_final:
        return normalized_final

    normalized_partial = (partial_transcript or "").strip()
    if timeout_like_end and allow_partial_on_timeout_like_end and normalized_partial:
        return normalized_partial

    return None
