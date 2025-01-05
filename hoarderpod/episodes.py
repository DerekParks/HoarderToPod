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

    def get_job_ids(self) -> set[str]:
        """Get the episode with a TTS job id.

        Returns:
                set[str]: The list of episode ids
        """
        with Session() as session:
            return {episode.tts_job_id for episode in session.query(Episode).all() if episode.tts_job_id}

    def null_episodes_that_tts_doesnt_know_about(self, ongoing_jobs: set[str]) -> list[tuple[str, str]]:
        """As a failsafe, make sure the TTS service still knows about episodes that have a job id but no mp3.

        Args:
            ongoing_jobs: The list of ongoing jobs

        Returns:
            list[tuple[str, str]]: The list of episodes that have a job id but no mp3
        """
        result = []
        with Session() as session:
            waiting_episodes = session.query(Episode).filter(Episode.tts_job_id != None, Episode.mp3 == None)
            for episode in waiting_episodes:
                if episode.tts_job_id not in ongoing_jobs:
                    episode.tts_job_id = None
                    result.append((episode.id, episode.tts_job_id))
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
