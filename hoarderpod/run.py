"""
Main logic/glue for polling hoarder and generating podcast feed
"""

import os
from datetime import datetime, timezone

import html2text
import newspaper
from feedgen.feed import FeedGenerator

from hoarderpod.config import Config
from hoarderpod.episodes import Episode, EpisodeOps
from hoarderpod.hoarder_service import HoarderService
from hoarderpod.tts_service import TTSService
from hoarderpod.utils import horder_dt_to_py, oxford_join, to_local_datetime

# Initialize services
tts_service = TTSService()
hoarder_service = HoarderService()
episode_ops = EpisodeOps()


def get_episode_dict(bookmark: dict) -> dict:
    """Get the episode dict including text, title, description, and authors of a bookmark.

    Args:
        bookmark: The bookmark dict from Hoarder

    Returns:
        dict: The episode dict including text, title, description, and authors of the bookmark
    """
    content = bookmark["content"]
    url = content["url"]
    authors = []
    newspaper_title = None
    newspaper_text = None
    newspaper_description = None
    try:
        article = newspaper.article(url)
        authors = article.authors
        newspaper_title = article.title
        newspaper_text = article.text
        newspaper_description = article.meta_description
    except Exception as e:
        print(f"Error parsing article {url}: {e} with newspaper4k")

    h = html2text.HTML2Text()
    h.ignore_links = True

    html2text_text = h.handle(content["htmlContent"]) if content["htmlContent"] else None

    if newspaper_text is None or len(html2text_text.split()) > len(newspaper_text.split()):
        text = html2text_text
    else:
        text = newspaper_text

    if newspaper_title is None or len(content["title"]) > len(newspaper_title):
        title = content["title"]
    else:
        title = newspaper_title

    if newspaper_description is None or len(content["description"]) > len(newspaper_description):
        description = content["description"]
    else:
        description = newspaper_description

    return {
        "id": bookmark["id"],
        "title": title,
        "description": description,
        "text": text,
        "authors": authors,
        "url": url,
        "createdAt": horder_dt_to_py(bookmark["createdAt"]),
        "crawledAt": horder_dt_to_py(bookmark["content"]["crawledAt"]),
    }


def episode_to_tts_text(episode: Episode, max_length: int | None = None) -> str:
    """Get the text to be used for TTS from an episode dict.

    Args:
        episode: The episode to get the text for
        max_length: The maximum length of the text to return (useful testing and not having to wait for TTS)
    """
    by_line = f"Written By {oxford_join(episode.authors)}" if len(episode.authors) > 0 else ""
    text = episode.text[:max_length] if max_length else episode.text
    return f"{episode.title}\n{by_line}\n\n{text}"


def gen_feed(episodes: list[Episode], root_url: str) -> str:
    """Generate an RSS feed of the bookmarks.

    Args:
        episodes: The list of episodes to include in the feed
        root_url: The root URL of the Hoarder instance

    Returns:
        str: The path to the RSS feed
    """
    fg = FeedGenerator()
    fg.id(Config.HOARDER_ROOT_URL)
    fg.title("Hoarder Articles")
    fg.link(href=Config.HOARDER_ROOT_URL, rel="alternate")
    fg.language("en")
    fg.description("Hoarder Articles")
    fg.load_extension("podcast")
    fg.podcast.itunes_author("Hoarder")
    fg.podcast.itunes_image(root_url + "cover.jpg")

    for episode in episodes:
        fe = fg.add_entry()
        fe.id(episode.id)
        fe.title(episode.title)
        fe.link({"href": episode.url, "rel": "alternate"})
        fe.description(episode.url + "<br>" + episode.description)
        fe.published(episode.created_at.replace(tzinfo=timezone.utc))
        fe.updated(episode.crawled_at.replace(tzinfo=timezone.utc))

        fe.author({"name": oxford_join(episode.authors)})
        fe.enclosure(root_url + f"audio/{os.path.basename(episode.mp3)}", 0, "audio/mpeg")
        fe.podcast.itunes_image(root_url + "cover.jpg")

    return fg.rss_str(pretty=True)


def update_db_with_new_episodes(bookmarks: list[dict]) -> None:
    """Update the SQL database with bookmarks from hoarder.

    Args:
        bookmarks: The list of bookmarks to update the database with
    """

    known_ids = episode_ops.get_episode_ids()

    for bookmark in bookmarks:
        if (
            bookmark["content"]["crawledAt"] is None
            or "url" not in bookmark["content"]
            or bookmark["content"]["url"] is None
        ):
            continue

        if bookmark["id"] in known_ids:
            continue

        episode_dict = get_episode_dict(bookmark)

        if episode_dict["text"] is None:
            continue

        episode = Episode(
            id=bookmark["id"],
            title=episode_dict["title"],
            description=episode_dict["description"],
            text=episode_dict["text"],
            url=episode_dict["url"],
            authors=episode_dict["authors"],
            created_at=episode_dict["createdAt"],
            crawled_at=episode_dict["crawledAt"],
        )
        episode_ops.add_episode(episode)


def submit_tts_request_for_episodes(episodes: list[Episode]) -> None:
    """Submit the TTS request for the episodes.

    Args:
        episodes: The list of episodes to submit the TTS request for
    """
    for episode in episodes:
        tts_job_id = tts_service.submit_tts(episode_to_tts_text(episode))
        episode_ops.mark_tts_submitted(episode.id, tts_job_id)


def download_completed_tts_jobs(completed_jobs: list[str]):
    """Download the mp3 for the completed TTS jobs and update the database.

    Args:
        completed_jobs: The list of completed job ids
    """
    for job_id in completed_jobs:
        mp3_path = tts_service.download_mp3(job_id)
        tts_service.delete_job(job_id)
        episode_ops.mark_tts_completed(job_id, os.path.basename(mp3_path))


def filter_job_ids_to_ones_we_know_about(job_ids: list[str]) -> list[str]:
    """Filter the job ids to ones we know about.

    Args:
        job_ids: The list of job ids to filter

    Returns:
        list[str]: The list of job ids we know about
    """
    known_job_ids = episode_ops.get_job_ids()
    result = []

    for job_id in job_ids:
        if job_id in known_job_ids:
            result.append(job_id)
        else:
            print("Removing unknown tts job with id", job_id)
            tts_service.delete_job(job_id)
    return result


def tts_pending_and_completed_update() -> None:
    """Update the TTS service and the database."""
    completed_jobs, ongoing_jobs = tts_service.get_jobs()

    completed_jobs = filter_job_ids_to_ones_we_know_about(completed_jobs)

    download_completed_tts_jobs(completed_jobs)
    nulled_tts_jobs = episode_ops.null_episodes_that_tts_doesnt_know_about(ongoing_jobs)
    for episode_id, tts_job_id in nulled_tts_jobs:
        print(f"Episode {episode_id} has a job id {tts_job_id} but the TTS service doesn't know about it.")


def main_poll_loop(cutoff_date: datetime | None = None, max_episodes: int | None = None) -> None:
    """Main function to run the script.

    Args:
        cutoff_date: The date to stop updating the database at
        max_episodes: The maximum number of episodes to update the database with
    """

    last_episode_date = episode_ops.get_latest_episode_date()
    print(f"Last episode date: {last_episode_date}")
    if cutoff_date is None or last_episode_date > cutoff_date:
        cutoff_date = last_episode_date
    print(f"Cutoff date: {cutoff_date}")

    update_db_with_new_episodes(hoarder_service.get_bookmarks(cutoff_date, max_episodes))

    if tts_service.check_health():
        tts_pending_and_completed_update()

        episodes_to_tts = episode_ops.get_episodes_to_tts()[: Config.TTS_BATCH_SIZE]

        submit_tts_request_for_episodes(episodes_to_tts)

    else:
        print("TTS service is not healthy, skipping TTS request")


def poll_hoarder_and_tts():
    """Poll hoarder and send out TTS jobs"""

    main_poll_loop(Config.EPISODES_CUTOFF_DATE, Config.EPISODES_PULL_MAX)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--cutoff-date", type=str, required=False, default=None, help="Only pull articles after this date"
    )
    parser.add_argument(
        "-m", "--max-episodes", type=int, required=False, default=None, help="Only pull this many episodes"
    )

    args = parser.parse_args()

    main_poll_loop(to_local_datetime(args.cutoff_date), args.max_episodes)
