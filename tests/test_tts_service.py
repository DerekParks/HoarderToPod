import os

import pytest
import requests

from hoarderpod.config import Config
from hoarderpod.tts_service import TTSService


@pytest.fixture
def tts_service():
    return TTSService()

@pytest.fixture
def mock_config(monkeypatch):
    monkeypatch.setattr(Config, 'TTS_ROOT_URL', 'http://test-tts-service.com')
    monkeypatch.setattr(Config, 'MP3_STORAGE_PATH', '/tmp/test_mp3')
    monkeypatch.setattr(Config, 'TTS_MODEL', 'test-model')
    monkeypatch.setattr(Config, 'TTS_VOICE', 'test-voice')

def test_init(mock_config, tmp_path):
    Config.MP3_STORAGE_PATH = str(tmp_path)
    service = TTSService()

    assert service.root_url == 'http://test-tts-service.com'
    assert service.mp3_storage_path == str(tmp_path)
    assert os.path.exists(service.mp3_storage_path)

def test_submit_tts(requests_mock, tts_service):
    expected_job_id = "test-job-123"
    requests_mock.post(
        tts_service.synthesize_path,
        json={"job_id": expected_job_id}
    )

    job_id = tts_service.submit_tts("Test text")
    assert job_id == expected_job_id

def test_submit_tts_error(requests_mock, tts_service):
    requests_mock.post(
        tts_service.synthesize_path,
        status_code=500
    )

    with pytest.raises(requests.exceptions.HTTPError):
        tts_service.submit_tts("Test text")

def test_get_jobs(requests_mock, tts_service):
    mock_response = {
        "jobs": [
            {"job_id": "job1", "status": "completed"},
            {"job_id": "job2", "status": "processing"},
            {"job_id": "job3", "status": "completed"}
        ]
    }
    requests_mock.get(tts_service.jobs_path, json=mock_response)

    completed, ongoing = tts_service.get_jobs()
    assert completed == ["job1", "job3"]
    assert ongoing == ["job2"]

def test_download_mp3(requests_mock, tts_service, tmp_path):
    job_id = "test-job-123"
    test_content = b"fake mp3 content"

    # Set temporary storage path
    tts_service.mp3_storage_path = str(tmp_path)

    requests_mock.get(
        tts_service.download_path.format(job_id=job_id),
        content=test_content
    )

    saved_path = tts_service.download_mp3(job_id)
    assert os.path.exists(saved_path)
    with open(saved_path, 'rb') as f:
        assert f.read() == test_content

def test_delete_job(requests_mock, tts_service):
    job_id = "test-job-123"
    requests_mock.delete(f"{tts_service.jobs_path}/{job_id}")

    # Should not raise any exception
    tts_service.delete_job(job_id)

def test_delete_job_error(requests_mock, tts_service):
    job_id = "test-job-123"
    requests_mock.delete(
        f"{tts_service.jobs_path}/{job_id}",
        status_code=500
    )

    with pytest.raises(requests.exceptions.HTTPError):
        tts_service.delete_job(job_id)

def test_check_health_success(requests_mock, tts_service):
    requests_mock.get(tts_service.health_path, status_code=200)
    assert tts_service.check_health() is True

def test_check_health_failure(requests_mock, tts_service):
    requests_mock.get(tts_service.health_path, status_code=500)
    assert tts_service.check_health() is False

def test_root_url_trailing_slash(mock_config):
    Config.TTS_ROOT_URL = 'http://test-tts-service.com/'
    service = TTSService()
    assert service.root_url == 'http://test-tts-service.com'
