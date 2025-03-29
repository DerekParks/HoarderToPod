"""
Configuration for the application
"""

import os

from hoarderpod.utils import to_local_datetime, remove_www


class Config:
    """Configuration for the application."""

    TTS_ROOT_URL = os.getenv("TTS_ROOT_URL", "http://localhost:5001")
    TTS_MODEL = os.getenv("TTS_MODEL", "kokoro")
    TTS_VOICE = os.getenv("TTS_VOICE", "af_heart")
    MP3_STORAGE_PATH = os.path.join(os.path.dirname(__file__), os.getenv("MP3_STORAGE_PATH", "../audio"))
    POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "10"))
    FLASK_ENV = os.getenv("FLASK_ENV")
    PORT = int(os.getenv("PORT", 5002))

    HOARDER_API_KEY = os.getenv("HOARDER_API_KEY")
    HOARDER_ROOT_URL = os.getenv("HOARDER_ROOT_URL", "http://localhost:3000")
    assert HOARDER_API_KEY is not None, "HOARDER_API_KEY is not set"

    if HOARDER_ROOT_URL.endswith("/"):
        HOARDER_ROOT_URL = HOARDER_ROOT_URL[:-1]

    DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///hoarder_episodes.db")

    EPISODES_CUTOFF_DATE = os.getenv("EPISODES_CUTOFF_DATE")
    EPISODES_PULL_MAX = os.getenv("EPISODES_PULL_MAX")

    if EPISODES_CUTOFF_DATE:
        EPISODES_CUTOFF_DATE = to_local_datetime(EPISODES_CUTOFF_DATE)

    if EPISODES_PULL_MAX:
        EPISODES_PULL_MAX = int(EPISODES_PULL_MAX)

    TTS_BATCH_SIZE = int(os.getenv("TTS_BATCH_SIZE", "10"))
    ARCHIVE_PH_DOMAINS = os.getenv("ARCHIVE_PH_DOMAINS") # Comma separated list of domains to scrape from archive.ph
    if ARCHIVE_PH_DOMAINS:
        ARCHIVE_PH_DOMAINS = set(remove_www(domain.strip()) for domain in ARCHIVE_PH_DOMAINS.split(","))
    else:
        ARCHIVE_PH_DOMAINS = set()
