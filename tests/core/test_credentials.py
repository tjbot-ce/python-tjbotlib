from pathlib import Path

import pytest

from tjbot.utils.errors import TJBotError
from tjbot.utils.credentials import (
    load_azure_credentials,
    load_google_cloud_credentials,
    resolve_credentials_path,
)


def test_resolve_credentials_path_prefers_provided_path(tmp_path):
    cred_file = tmp_path / 'custom.env'
    cred_file.write_text('FOO=bar\n', encoding='utf-8')

    resolved = resolve_credentials_path('azure-credentials.env', str(cred_file))
    assert resolved == str(cred_file)


def test_resolve_credentials_path_not_found_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('HOME', str(tmp_path / 'home-empty'))
    with pytest.raises(TJBotError, match='Credentials file azure-credentials.env not found'):
        resolve_credentials_path('azure-credentials.env')


def test_load_google_cloud_credentials_sets_env(tmp_path):
    cred_file = tmp_path / 'google-credentials.json'
    cred_file.write_text('{"type": "service_account"}\n', encoding='utf-8')

    out = load_google_cloud_credentials(str(cred_file))
    assert out['credentialsPath'] == str(cred_file)


def test_load_azure_credentials_parses_env(tmp_path):
    cred_file = tmp_path / 'azure-credentials.env'
    cred_file.write_text(
        'AZURE_VISION_KEY=test_key\nAZURE_VISION_ENDPOINT=https://example.cognitiveservices.azure.com/\n',
        encoding='utf-8',
    )

    creds = load_azure_credentials(str(cred_file))
    assert creds['visionKey'] == 'test_key'
    assert creds['visionEndpoint'] == 'https://example.cognitiveservices.azure.com/'
