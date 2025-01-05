"""
Service for interacting with the Hoarder API
"""

from collections.abc import Generator
from datetime import datetime

import requests

from hoarderpod.config import Config
from hoarderpod.utils import horder_dt_to_py


class PATHS:
    """Paths for the TTS service."""

    BOOKMARK_PATH = "api/v1/bookmarks"


class HoarderService:
    """Service for interacting with the Hoarder API."""

    def __init__(self):
        self.root_url = Config.HOARDER_ROOT_URL
        self.api_key = Config.HOARDER_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        self.bookmark_path = f"{self.root_url}/{PATHS.BOOKMARK_PATH}"

    def get_one_page_bookmarks(self, cursor: str | None = None):
        """Get bookmarks from Hoarder.

        Args:
            cursor: Optional cursor to get the next page of bookmarks
        """
        url = self.bookmark_path + (f"?cursor={cursor}" if cursor is not None else "")
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        res_json = response.json()
        bookmarks = res_json["bookmarks"]
        cursor = res_json["nextCursor"]
        return bookmarks, cursor

    def get_bookmarks(
        self, before_date: datetime | None = None, max_episodes: int | None = None
    ) -> Generator[dict, None, None]:
        """
        Generator to get all bookmarks from Hoarder.

        Args:
            before_date: Optional datetime to stop yielding bookmarks when createdAt is before this date
            max_episodes: Optional int to stop yielding bookmarks after this many episodes
        """
        cursor = None
        episodes_yielded = 0
        while True:
            bookmarks, cursor = self.get_one_page_bookmarks(cursor)
            for bookmark in bookmarks:
                created_at = horder_dt_to_py(bookmark["createdAt"])

                if before_date and created_at <= before_date:
                    return
                yield bookmark
                episodes_yielded += 1
                if max_episodes and episodes_yielded >= max_episodes:
                    return
            if cursor is None:
                break
