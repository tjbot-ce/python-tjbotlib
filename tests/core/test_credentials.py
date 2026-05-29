import pytest

from tjbot.utils.errors import TJBotError
from tjbot.utils.credentials import (
    load_azure_credentials,
    load_google_cloud_credentials,
    load_ibm_watson_cloud_credentials,
    resolve_credentials_path,
)


def test_resolve_credentials_path_prefers_provided_path(tmp_path):
    cred_file = tmp_path / "custom.env"
    cred_file.write_text("FOO=bar\n", encoding="utf-8")

    resolved = resolve_credentials_path("azure-credentials.env", str(cred_file))
    assert resolved == str(cred_file)


def test_resolve_credentials_path_not_found_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home-empty"))
    with pytest.raises(
        TJBotError, match="Credentials file azure-credentials.env not found"
    ):
        resolve_credentials_path("azure-credentials.env")


def test_load_google_cloud_credentials_sets_env(tmp_path):
    cred_file = tmp_path / "google-credentials.json"
    cred_file.write_text(
        '{"type": "service_account", "project_id": "demo-project"}\n',
        encoding="utf-8",
    )

    out = load_google_cloud_credentials(str(cred_file))
    assert out["credentialsPath"] == str(cred_file)


def test_load_azure_credentials_parses_env(tmp_path):
    cred_file = tmp_path / "azure-credentials.env"
    cred_file.write_text(
        "AZURE_VISION_KEY=test_key\nAZURE_VISION_ENDPOINT=https://example.cognitiveservices.azure.com/\n",
        encoding="utf-8",
    )

    creds = load_azure_credentials(str(cred_file))
    assert creds["visionKey"] == "test_key"
    assert creds["visionEndpoint"] == "https://example.cognitiveservices.azure.com/"


def test_loads_azure_credentials_from_tmp_and_exports_vars_to_environment(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.delenv("AZURE_VISION_KEY", raising=False)
    monkeypatch.delenv("AZURE_VISION_ENDPOINT", raising=False)

    cred_file = tmp_path / "azure-credentials.env"
    cred_file.write_text(
        "AZURE_SPEECH_KEY=test-speech-key\n"
        "AZURE_SPEECH_REGION=eastus\n"
        "AZURE_VISION_KEY=test-vision-key\n"
        "AZURE_VISION_ENDPOINT=https://example.cognitiveservices.azure.com/\n",
        encoding="utf-8",
    )

    creds = load_azure_credentials(str(cred_file))
    assert creds["speechKey"] == "test-speech-key"
    assert creds["speechRegion"] == "eastus"
    assert creds["visionKey"] == "test-vision-key"
    assert creds["visionEndpoint"] == "https://example.cognitiveservices.azure.com/"


def test_loads_google_cloud_credentials_path_from_tmp_and_sets_google_application_credentials(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    cred_file = tmp_path / "google-credentials.json"
    cred_file.write_text(
        '{"type":"service_account","project_id":"test-project"}\n', encoding="utf-8"
    )

    out = load_google_cloud_credentials(str(cred_file))
    assert out["credentialsPath"] == str(cred_file)


def test_loads_ibm_watson_credentials_from_tmp_and_exports_vars_to_environment(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("SPEECH_TO_TEXT_APIKEY", raising=False)
    monkeypatch.delenv("SPEECH_TO_TEXT_IAM_APIKEY", raising=False)
    monkeypatch.delenv("SPEECH_TO_TEXT_URL", raising=False)
    monkeypatch.delenv("SPEECH_TO_TEXT_AUTH_TYPE", raising=False)

    cred_file = tmp_path / "ibm-credentials.env"
    cred_file.write_text(
        "SPEECH_TO_TEXT_APIKEY=test-stt-apikey\n"
        "SPEECH_TO_TEXT_IAM_APIKEY=test-stt-iam-apikey\n"
        "SPEECH_TO_TEXT_URL=https://api.us-south.speech-to-text.watson.cloud.ibm.com\n"
        "SPEECH_TO_TEXT_AUTH_TYPE=iam\n",
        encoding="utf-8",
    )

    load_ibm_watson_cloud_credentials(str(cred_file))
