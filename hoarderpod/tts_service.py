"""
Service for interacting with the TTS service
"""

import os

import requests

from hoarderpod.config import Config


class PATHS:
    """Paths for the TTS service."""

    SYNTHESIZE = "tts/synthesize"
    JOBS = "tts/jobs"
    DOWNLOAD = "tts/jobs/{job_id}/download"
    HEALTH = "health/check"


class TTSService:
    """Service for interacting with the TTS service."""

    def __init__(self):
        self.root_url = Config.TTS_ROOT_URL
        if self.root_url.endswith("/"):
            self.root_url = self.root_url[:-1]

        self.mp3_storage_path = Config.MP3_STORAGE_PATH
        if not os.path.exists(self.mp3_storage_path):
            os.makedirs(self.mp3_storage_path)

        self.synthesize_path = f"{self.root_url}/{PATHS.SYNTHESIZE}"
        self.jobs_path = f"{self.root_url}/{PATHS.JOBS}"
        self.download_path = f"{self.root_url}/{PATHS.DOWNLOAD}"
        self.health_path = f"{self.root_url}/{PATHS.HEALTH}"

    def submit_tts(self, text: str) -> str:
        """Submit a TTS request and return the job id.

        Args:
            text: The text to be used for TTS

        Returns:
            str: The job id of the TTS request
        """
        response = requests.post(self.synthesize_path, json={"text": text})
        response.raise_for_status()
        return response.json()["job_id"]

    def get_jobs(self) -> tuple[list[str], list[str]]:
        """Get the TTS jobs from the TTS service.

        Returns:
            tuple[list[str], list[str]]: The list of completed and ongoing TTS jobs
        """
        response = requests.get(self.jobs_path)
        response.raise_for_status()
        res_json = response.json()["jobs"]
        completed_jobs = []
        ongoing_jobs = []
        for job in res_json:
            if job["status"].lower() == "completed":
                completed_jobs.append(job["job_id"])
            else:
                ongoing_jobs.append(job["job_id"])

        return completed_jobs, ongoing_jobs

    def download_mp3(self, job_id: str) -> str:
        """Download the mp3 for the job.

        Args:
            job_id: The job id to download the mp3 for

        Returns:
            str: The path where the mp3 was saved
        """
        response = requests.get(self.download_path.format(job_id=job_id))
        response.raise_for_status()
        saved_path = os.path.join(self.mp3_storage_path, f"{job_id}.mp3")
        with open(saved_path, "wb") as f:
            f.write(response.content)
        return saved_path

    def delete_job(self, job_id: str) -> None:
        """Delete the TTS job from the TTS service.

        Args:
            job_id: The job id to delete
        """
        response = requests.delete(f"{self.jobs_path}/{job_id}")
        response.raise_for_status()

    def check_health(self) -> bool:
        """Check the health of the TTS service."""
        response = requests.get(self.health_path)
        return response.status_code == 200
