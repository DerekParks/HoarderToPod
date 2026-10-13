from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from hoarderpod.episodes import Episode, EpisodeOps

with patch("apscheduler.schedulers.background.BackgroundScheduler.start"):
    from hoarderpod.api import app

pytestmark = pytest.mark.usefixtures("empty_db")


@pytest.fixture
def client():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(120):
        created_at = start + timedelta(hours=i)
        EpisodeOps().add_episode(
            Episode(id=f"ep{i:03d}", title=f"Title {i:03d}", created_at=created_at, crawled_at=created_at)
        )
    return app.test_client()


def _titles(html: str) -> list[str]:
    return [f"Title {i:03d}" for i in range(120) if f"Title {i:03d}" in html]


def test_first_page_is_newest_episodes(client):
    html = client.get("/").get_data(as_text=True)

    assert _titles(html) == [f"Title {i:03d}" for i in range(70, 120)]
    assert "Page 1 of 3" in html
    assert "120 episodes" in html


def test_middle_page_with_custom_page_size(client):
    html = client.get("/?page=3&per_page=20").get_data(as_text=True)

    assert _titles(html) == [f"Title {i:03d}" for i in range(60, 80)]
    assert "Page 3 of 6" in html
    assert 'href="?page=2&amp;per_page=20"' in html
    assert 'href="?page=4&amp;per_page=20"' in html


def test_page_past_the_end_shows_last_page(client):
    html = client.get("/?page=99").get_data(as_text=True)

    assert _titles(html) == [f"Title {i:03d}" for i in range(20)]
    assert "Page 3 of 3" in html


def test_empty_db_renders_single_empty_page(empty_db):
    html = app.test_client().get("/").get_data(as_text=True)

    assert "Page 1 of 1" in html
    assert "0 episodes" in html
