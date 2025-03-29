import pytest
import re
from datetime import datetime
import requests_mock
from unittest.mock import patch

from hoarderpod.archive_scraper import (
    get_random_user_agent,
    snapshot,
    _search,
    timemap,
    get_latest_snapshot,
)


def test_get_random_user_agent():
    """Test that get_random_user_agent returns a string from the USER_AGENTS list."""
    user_agent = get_random_user_agent()
    assert isinstance(user_agent, str)
    assert "Mozilla" in user_agent


@pytest.fixture
def mock_initial_response():
    """Mock response for the initial request to archive.ph."""
    return """
    <html>
    <form>
    <input type="hidden" name="submitid" value="test-submit-id-12345">
    </form>
    </html>
    """


@pytest.fixture
def mock_redirect_response():
    """Mock response for a redirect to an existing snapshot."""
    return """
    <html>
    <div>Saved from example.com on 12 Mar 2023 15:30:45</div>
    </html>
    """


@pytest.fixture
def mock_wip_response():
    """Mock response for a WIP URL."""
    return """
    <html>
    <script>document.location.replace("/wip/12345678");</script>
    </html>
    """


@pytest.fixture
def mock_complete_response():
    """Mock response for a completed archive."""
    return """
    <html>
    <script>document.location.replace("/12345678");</script>
    </html>
    """


@pytest.fixture
def mock_search_response():
    """Mock response for a search query."""
    return """
    <html>
    <div>12 Mar 2023 15:30</div></a></div></div><div><a href="/abc123">
    <div>15 Apr 2023 10:25</div></a></div></div><div><a href="/def456">
    </html>
    """


def test_snapshot_existing(mock_initial_response, mock_redirect_response):
    """Test snapshot function when archive already exists."""
    with requests_mock.Mocker() as m:
        # Mock the initial request
        m.get("https://archive.ph", text=mock_initial_response)

        # Mock the submit request to redirect to existing snapshot
        m.post(
            "https://archive.ph/submit/",
            status_code=302,
            headers={"Location": "/abc123"}
        )

        # Mock the request to the snapshot
        m.get("https://archive.ph/abc123", text=mock_redirect_response)

        result = snapshot("https://example.com", complete=False)

        assert result["url"] == "https://archive.ph/abc123"
        assert "cached_date" in result
        assert result["cached_date"] == "12 Mar 2023 15:30:45"


def test_snapshot_new_complete(mock_initial_response, mock_wip_response, mock_complete_response):
    """Test snapshot function when creating a new archive and waiting for completion."""
    with requests_mock.Mocker() as m:
        # Mock the initial request
        m.get("https://archive.ph", text=mock_initial_response)

        # Mock the submit request to return a WIP URL
        m.post("https://archive.ph/submit/", text=mock_wip_response)

        # Mock the WIP URL request to redirect to the completed URL
        m.get("https://archive.ph/wip/12345678", text=mock_complete_response)

        # Mock the completed URL request
        m.get("https://archive.ph/12345678", text="<html>Archived content</html>")

        with patch("time.sleep"):  # Skip sleeping
            result = snapshot("https://example.com")

            assert "url" in result
            assert result["url"] == "https://archive.ph/12345678"


def test_snapshot_new_incomplete(mock_initial_response, mock_wip_response):
    """Test snapshot function when creating a new archive without waiting for completion."""
    with requests_mock.Mocker() as m:
        # Mock the initial request
        m.get("https://archive.ph", text=mock_initial_response)

        # Mock the submit request to return a WIP URL
        m.post("https://archive.ph/submit/", text=mock_wip_response)

        result = snapshot("https://example.com", complete=False)

        assert "url" in result
        assert result["url"] == "https://archive.ph/12345678"
        assert "wip" in result
        assert result["wip"] == "https://archive.ph/wip/12345678"


def test_search(mock_search_response):
    """Test _search function."""
    with requests_mock.Mocker() as m:
        # Mock the search request
        m.get("https://archive.ph/search/?q=https://example.com", text=mock_search_response)

        results = _search("https://example.com", "https://archive.ph", {"User-Agent": "test"})

        assert len(results) == 2
        print("here!", results[0])
        assert results[0] == ("12 Mar 2023 15:30", "/abc123")
        assert results[1] == ("15 Apr 2023 10:25", "/def456")


def test_timemap(mock_search_response):
    """Test timemap function."""
    with requests_mock.Mocker() as m:
        # Mock the search request
        m.get("https://archive.ph/search/?q=https://example.com", text=mock_search_response)

        with patch("builtins.print"):  # Suppress print statements
            results = timemap("https://example.com")

            assert len(results) == 2
            assert results[0]["url"] == "/abc123"
            assert results[0]["date"] == "12 Mar 2023 15:30"
            assert results[1]["url"] == "/def456"
            assert results[1]["date"] == "15 Apr 2023 10:25"


def test_timemap_no_results(mock_search_response):
    """Test timemap function when no results are found."""
    with requests_mock.Mocker() as m:
        # Mock the initial search with no results
        m.get("https://archive.ph/search/?q=https://example.com", text="<html></html>")

        # Mock the follow-up search with stripped query parameters
        m.get("https://archive.ph/search/?q=https://example.com", text=mock_search_response)

        with patch("builtins.print"):  # Suppress print statements
            results = timemap("https://example.com")

            assert len(results) == 2


def test_get_latest_snapshot(mock_search_response):
    """Test get_latest_snapshot function."""
    with requests_mock.Mocker() as m:
        # Mock the search request
        m.get("https://archive.ph/search/?q=https://example.com", text=mock_search_response)

        with patch("builtins.print"):  # Suppress print statements
            result = get_latest_snapshot("https://example.com")

            assert result == "/def456"  # The latest date in the mock response


def test_get_latest_snapshot_no_results():
    """Test get_latest_snapshot function when no results are found."""
    with requests_mock.Mocker() as m:
        # Mock the search request with no results
        m.get("https://archive.ph/search/?q=https://example.com", text="<html></html>")

        # Mock the follow-up search with stripped query parameters
        m.get(
            "https://archive.ph/search/?q=https://example.com",
            text="<html></html>"
        )

        with patch("builtins.print"):  # Suppress print statements
            result = get_latest_snapshot("https://example.com")

            assert result is None
