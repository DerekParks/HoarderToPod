from unittest.mock import Mock, patch

from hoarderpod.article_parse import transform_markdown, fetch_asset_content, get_episode_dict


def test_markdown_strip_test():
    test_text = """
# Main Title
This is some content

## Section Header
More content here

* List item
* Another item

This *book title* is in italics
    """
    markdown_text = transform_markdown(test_text)

    assert "Headline:" in markdown_text
    assert "Section:" in markdown_text
    assert "* List item" in markdown_text
    assert "italic:" in markdown_text


@patch("hoarderpod.article_parse.requests.get")
@patch("hoarderpod.article_parse.Config")
def test_fetch_asset_content_success(mock_config, mock_requests_get):
    """Test successfully fetching asset content from Hoarder API."""
    # Setup mocks
    mock_config.HOARDER_ROOT_URL = "http://test.com"
    mock_config.HOARDER_API_KEY = "test-key"

    mock_response = Mock()
    mock_response.text = "<html><body>Test Article Content</body></html>"
    mock_response.raise_for_status = Mock()
    mock_requests_get.return_value = mock_response

    # Test
    result = fetch_asset_content("test-asset-id")

    # Verify
    assert result == "<html><body>Test Article Content</body></html>"
    mock_requests_get.assert_called_once_with(
        "http://test.com/api/v1/assets/test-asset-id",
        headers={
            "Authorization": "Bearer test-key",
            "Content-Type": "application/json",
        }
    )


@patch("hoarderpod.article_parse.requests.get")
@patch("hoarderpod.article_parse.Config")
def test_fetch_asset_content_failure(mock_config, mock_requests_get):
    """Test handling of failed asset fetch."""
    # Setup mocks
    mock_config.HOARDER_ROOT_URL = "http://test.com"
    mock_config.HOARDER_API_KEY = "test-key"

    mock_requests_get.side_effect = Exception("Network error")

    # Test
    result = fetch_asset_content("test-asset-id")

    # Verify
    assert result is None


@patch("hoarderpod.article_parse.parse_with_newspaper")
@patch("hoarderpod.article_parse.html2text")
def test_get_episode_dict_with_inline_html(mock_html2text, mock_newspaper):
    """Test get_episode_dict when htmlContent is inline (regular articles)."""
    # Setup mocks
    mock_newspaper.return_value = {
        "authors": ["Test Author"],
        "title": "Test Title",
        "text": "Short text",
        "description": "Test description"
    }
    mock_html2text.return_value = "This is a much longer article text content"

    # Test data - regular article with inline htmlContent
    bookmark = {
        "id": "test-id",
        "createdAt": "2026-02-05T16:46:22.000Z",
        "content": {
            "url": "https://example.com/article",
            "title": "Test Article",
            "description": "Test description",
            "htmlContent": "<html><body>Article content</body></html>",
            "crawledAt": "2026-02-05T16:46:23.000Z"
        }
    }

    # Test
    result = get_episode_dict(bookmark)

    # Verify
    assert result["id"] == "test-id"
    assert result["title"] == "Test Article"
    assert result["text"] == "This is a much longer article text content"
    assert result["authors"] == ["Test Author"]
    mock_html2text.assert_called_once_with("<html><body>Article content</body></html>")


@patch("hoarderpod.article_parse.fetch_asset_content")
@patch("hoarderpod.article_parse.parse_with_newspaper")
@patch("hoarderpod.article_parse.html2text")
def test_get_episode_dict_with_asset_content(mock_html2text, mock_newspaper, mock_fetch_asset):
    """Test get_episode_dict when htmlContent is null and needs asset fetch (SingleFile articles)."""
    # Setup mocks
    mock_newspaper.return_value = {
        "authors": [],
        "title": None,
        "text": None,
        "description": None
    }
    mock_fetch_asset.return_value = "<html><body>Full SingleFile article content here</body></html>"
    mock_html2text.return_value = "Full SingleFile article content here with lots of text"

    # Test data - SingleFile article with null htmlContent and contentAssetId
    bookmark = {
        "id": "singlefile-id",
        "createdAt": "2026-02-05T16:46:22.000Z",
        "content": {
            "url": "https://example.com/article",
            "title": "Gmail Article",
            "description": None,
            "htmlContent": None,  # This is null for SingleFile articles
            "contentAssetId": "bc595762-5424-4ed8-8a08-487ebb00634e",
            "precrawledArchiveAssetId": "91adcf83-bc10-4a44-87ea-893f60e57bd0",
            "crawledAt": "2026-02-05T16:46:23.000Z"
        }
    }

    # Test
    result = get_episode_dict(bookmark)

    # Verify
    assert result["id"] == "singlefile-id"
    assert result["title"] == "Gmail Article"
    assert result["text"] == "Full SingleFile article content here with lots of text"

    # Verify asset was fetched
    mock_fetch_asset.assert_called_once_with("bc595762-5424-4ed8-8a08-487ebb00634e")
    mock_html2text.assert_called_once_with("<html><body>Full SingleFile article content here</body></html>")


@patch("hoarderpod.article_parse.fetch_asset_content")
@patch("hoarderpod.article_parse.parse_with_newspaper")
@patch("hoarderpod.article_parse.html2text")
def test_get_episode_dict_with_precrawled_archive_asset(mock_html2text, mock_newspaper, mock_fetch_asset):
    """Test get_episode_dict falls back to precrawledArchiveAssetId if contentAssetId is missing."""
    # Setup mocks
    mock_newspaper.return_value = {
        "authors": [],
        "title": None,
        "text": None,
        "description": None
    }
    mock_fetch_asset.return_value = "<html><body>Archive content</body></html>"
    mock_html2text.return_value = "Archive content text"

    # Test data - only precrawledArchiveAssetId available
    bookmark = {
        "id": "archive-id",
        "createdAt": "2026-02-05T16:46:22.000Z",
        "content": {
            "url": "https://example.com/article",
            "title": "Archive Article",
            "description": None,
            "htmlContent": None,
            "precrawledArchiveAssetId": "91adcf83-bc10-4a44-87ea-893f60e57bd0",
            "crawledAt": "2026-02-05T16:46:23.000Z"
        }
    }

    # Test
    result = get_episode_dict(bookmark)

    # Verify fallback to precrawledArchiveAssetId
    mock_fetch_asset.assert_called_once_with("91adcf83-bc10-4a44-87ea-893f60e57bd0")
