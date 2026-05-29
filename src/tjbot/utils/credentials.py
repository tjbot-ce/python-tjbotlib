import os
from pathlib import Path
from typing import Dict

from .errors import TJBotError


def resolve_credentials_path(filename: str, provided_path: str = "") -> str:
    if provided_path:
        path = Path(provided_path)
        if not path.exists():
            raise TJBotError(f"Credentials file not found at: {provided_path}")
        return str(path)

    default_paths = [
        Path.cwd() / filename,
        Path.home() / ".tjbot" / filename,
    ]

    for path in default_paths:
        if path.exists():
            return str(path)

    raise TJBotError(
        f"Credentials file {filename} not found. Place credentials at ./{filename} or ~/.tjbot/{filename}"
    )


def _parse_env_credentials_file(credentials_path: str) -> Dict[str, str]:
    raw: Dict[str, str] = {}
    with open(credentials_path, "r", encoding="utf-8") as file:
        for line in file:
            entry = line.strip()
            if not entry or entry.startswith("#"):
                continue

            key, sep, value = entry.partition("=")
            if not sep:
                continue

            raw[key.strip()] = value.strip()

    return raw


def _load_credentials_into_environment(credentials: Dict[str, str]) -> None:
    for key, value in credentials.items():
        os.environ[key] = value


def load_azure_credentials(provided_path: str = "") -> Dict[str, str]:
    credentials_path = resolve_credentials_path("azure-credentials.env", provided_path)
    raw = _parse_env_credentials_file(credentials_path)
    _load_credentials_into_environment(raw)
    return {
        "speechKey": raw.get("AZURE_SPEECH_KEY", ""),
        "speechRegion": raw.get("AZURE_SPEECH_REGION", ""),
        "visionKey": raw.get("AZURE_VISION_KEY", ""),
        "visionEndpoint": raw.get("AZURE_VISION_ENDPOINT", ""),
    }


def load_google_cloud_credentials(provided_path: str = "") -> Dict[str, str]:
    credentials_path = resolve_credentials_path(
        "google-credentials.json", provided_path
    )
    if not Path(credentials_path).exists():
        raise TJBotError(
            f"Google Cloud credentials file not found at: {credentials_path}"
        )

    _load_credentials_into_environment(
        {"GOOGLE_APPLICATION_CREDENTIALS": credentials_path}
    )
    return {"credentialsPath": credentials_path}


def load_ibm_watson_cloud_credentials(provided_path: str = "") -> None:
    credentials_path = resolve_credentials_path("ibm-credentials.env", provided_path)
    raw = _parse_env_credentials_file(credentials_path)
    _load_credentials_into_environment(raw)
