from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from hoarderpod import run
from hoarderpod.episodes import Episode

pytestmark = pytest.mark.usefixtures("empty_db")


def _add_episode(episode_id: str, created_at: datetime, mp3: str | None = None) -> None:
    run.episode_ops.add_episode(
        Episode(id=episode_id, title=episode_id, created_at=created_at, crawled_at=created_at, mp3=mp3)
    )


def test_age_off_deletes_old_episodes_and_their_audio(tmp_path):
    now = datetime.now(timezone.utc)
    (tmp_path / "old.mp3").write_bytes(b"old")
    (tmp_path / "new.mp3").write_bytes(b"new")
    _add_episode("old-with-audio", now - timedelta(days=40), "old.mp3")
    _add_episode("old-without-audio", now - timedelta(days=40))
    _add_episode("new", now - timedelta(days=1), "new.mp3")

    with patch.object(run.tts_service, "mp3_storage_path", str(tmp_path)):
        run.age_off_episodes(now - timedelta(days=30))

    assert run.episode_ops.get_episode_ids() == {"new"}
    assert not (tmp_path / "old.mp3").exists()
    assert (tmp_path / "new.mp3").exists()


def test_retention_cutoff_disabled_when_unset():
    with patch.object(run.Config, "EPISODE_RETENTION_DAYS", None):
        assert run.retention_cutoff() is None


def test_poll_does_not_pull_bookmarks_older_than_retention_after_everything_ages_off():
    now = datetime.now(timezone.utc)
    _add_episode("ancient", now - timedelta(days=400))

    with (
        patch.object(run.Config, "EPISODE_RETENTION_DAYS", 30),
        patch.object(run.hoarder_service, "get_bookmarks", return_value=[]) as get_bookmarks,
    ):
        run.main_poll_loop(cutoff_date=None)

    assert run.episode_ops.get_episode_ids() == set()
    pulled_after = get_bookmarks.call_args.args[0]
    assert abs(pulled_after - (now - timedelta(days=30))) < timedelta(minutes=1)
