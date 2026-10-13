"""
Database operations for episodes
"""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from hoarderpod.config import Config
from hoarderpod.utils import to_utc

# Database setup
Base = declarative_base()
engine = create_engine(Config.DATABASE_URI)
Session = sessionmaker(bind=engine)


class Episode(Base):
    """Episode model."""

    __tablename__ = "episodes"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    text = Column(Text)
    authors = Column(JSON)
    created_at = Column(DateTime, nullable=False)
    url = Column(String)
    # don't add episodes that haven't been crawled yet
    crawled_at = Column(DateTime, nullable=False)
    tts_job_id = Column(String)
    mp3 = Column(String)


# Create tables if they don't exist
Base.metadata.create_all(engine)


class EpisodeOps:
    """Operations for the Episode model."""

    def get_episodes_with_mp3(self) -> list[Episode]:
        """Get the episodes with mp3.

        Returns:
            list[Episode]: The list of episodes with mp3
        """
        with Session() as session:
            return session.query(Episode).filter(Episode.mp3 != None).order_by(Episode.created_at.asc()).all()

    def get_episode_ids(self) -> set[str]:
        """Get the episode ids.

        Returns:
            set[str]: The list of episode ids
        """
        with Session() as session:
            return {episode.id for episode in session.query(Episode).all()}

    def get_episodes_to_tts(self) -> list[Episode]:
        """Get the episodes that haven't been processed by TTS yet.

        Returns:
            list[Episode]: The list of episodes that haven't been processed by TTS yet
        """
        with Session() as session:
            return session.query(Episode).filter(Episode.tts_job_id == None).order_by(Episode.created_at.asc()).all()

    def has_submitted_tts_jobs(self) -> bool:
        """Return True if there are episodes with a TTS job id but no mp3 yet."""
        with Session() as session:
            return (
                session.query(Episode)
                .filter(Episode.tts_job_id != None, Episode.mp3 == None)
                .first()
                is not None
            )

    def get_job_ids(self) -> set[str]:
        """Get the episode with a TTS job id.

        Returns:
                set[str]: The list of episode ids
        """
        with Session() as session:
            return {episode.tts_job_id for episode in session.query(Episode).all() if episode.tts_job_id}

    def null_episodes_that_tts_doesnt_know_about(self, known_jobs: set[str]) -> list[tuple[str, str]]:
        """Null the tts_job_id of local episodes whose job the TTS service no longer tracks.

        Args:
            known_jobs: The set of job ids the TTS service currently reports
                (union of completed and ongoing; failed/errored jobs should
                be excluded so they get retried).

        Returns:
            list[tuple[str, str]]: (episode_id, old_job_id) pairs that were nulled.
        """
        result = []
        with Session() as session:
            waiting_episodes = (
                session.query(Episode)
                .filter(Episode.tts_job_id != None, Episode.mp3 == None)
                .all()
            )
            for episode in waiting_episodes:
                if episode.tts_job_id not in known_jobs:
                    old_id = episode.tts_job_id
                    episode.tts_job_id = None
                    result.append((episode.id, old_id))
            session.commit()
        return result

    def mark_tts_completed(self, job_id: str, mp3_path: str):
        """Mark an episode as crawled.

        Args:
            job_id: The job id
            mp3_path: The mp3 path
        """
        with Session() as session:
            episode = session.query(Episode).filter_by(tts_job_id=job_id).first()
            episode.mp3 = mp3_path
            session.commit()

    def mark_tts_submitted(self, episode_id: str, job_id: str):
        """Mark an episode as submitted to TTS.

        Args:
            job_id: The job id
        """
        with Session() as session:
            episode = session.query(Episode).filter_by(id=episode_id).first()
            episode.tts_job_id = job_id
            session.commit()

    def add_episode(self, episode: Episode):
        """Add an episode to the database.

        Args:
            episode: The episode to add
        """
        with Session() as session:
            session.add(episode)
            session.commit()

    def delete_episode(self, episode_id: str) -> int:
        """Delete an episode from the database.

        Args:
            episode_id: The episode id
        """
        with Session() as session:
            result = session.query(Episode).filter(Episode.id == episode_id).delete()
            session.commit()
            return result

    def delete_episodes_created_before(self, cutoff: datetime) -> list[str | None]:
        """Delete episodes created before the cutoff.

        Args:
            cutoff: Naive UTC datetime; episodes created strictly before it are deleted

        Returns:
            list[str | None]: The mp3 filename of each deleted episode, None for those without audio
        """
        with Session() as session:
            expired = session.query(Episode).filter(Episode.created_at < cutoff)
            mp3s = [episode.mp3 for episode in expired]
            expired.delete()
            session.commit()
            return mp3s

    def get_episodes_page(self, page: int, per_page: int) -> tuple[list[Episode], int]:
        """Get one page of episodes, newest first.

        Args:
            page: 1-based page number
            per_page: The number of episodes per page

        Returns:
            tuple[list[Episode], int]: The episodes on the page and the total episode count
        """
        with Session() as session:
            query = session.query(Episode)
            total = query.count()
            episodes = query.order_by(Episode.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
            return episodes, total

    def get_all_episodes(self, sort_by_created_at: bool = False) -> list[Episode]:
        """Get all episodes.

        Returns:
            list[Episode]: The list of episodes
        """
        with Session() as session:
            if sort_by_created_at:
                return session.query(Episode).order_by(Episode.created_at.desc()).all()
            return session.query(Episode).all()

    def get_latest_episode_date(self) -> datetime | None:
        """Get the last episode.

        Returns:
            datetime: The last episode
        """
        with Session() as session:
            episode = session.query(Episode).order_by(Episode.created_at.desc()).first()
            return to_utc(episode.created_at) if episode else None

    def clear_tts(self, episode_id: str):
        """Clear the TTS job id and MP3 Path for an episode.

        Args:
            episode_id: The episode id to clear
        """
        with Session() as session:
            episode = session.query(Episode).filter_by(id=episode_id).first()
            episode.tts_job_id = None
            episode.mp3 = None
            session.commit()

    def get_episode_mp3(self, episode_id: str) -> str | None:
        """Get an episode's mp3 path by id.

        Args:
            episode_id: The episode id

        Returns:
            str: The mp3 path
        """
        with Session() as session:
            return session.query(Episode).filter_by(id=episode_id).first().mp3
