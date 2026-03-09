from unittest.mock import Mock, patch

from hoarderpod.article_parse import transform_markdown, fetch_asset_content, get_episode_dict, clean_text_for_tts, html2text, preprocess_html


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


def test_clean_text_for_tts():
    """Test that problematic Unicode characters are cleaned for TTS."""
    # Test non-breaking spaces
    text_with_nbsp = "This\xa0is\xa0text"
    cleaned = clean_text_for_tts(text_with_nbsp)
    assert "\xa0" not in cleaned
    assert cleaned == "This is text"

    # Test multiple spaces collapsed
    text_with_spaces = "This   has    many     spaces"
    cleaned = clean_text_for_tts(text_with_spaces)
    assert cleaned == "This has many spaces"

    # Test zero-width and other special spaces
    text_with_special = "Word\u200bwith\u2009special\u202fspaces"
    cleaned = clean_text_for_tts(text_with_special)
    assert "\u200b" not in cleaned
    assert "\u2009" not in cleaned
    assert "\u202f" not in cleaned

    # Test curly quotes/apostrophes converted to straight quotes
    text_with_curly = "It\u2019s a test\u2014won\u2019t work"  # curly apostrophes
    cleaned = clean_text_for_tts(text_with_curly)
    assert "\u2019" not in cleaned
    assert "It's a test" in cleaned
    assert "won't work" in cleaned

    # Test curly double quotes
    text_with_quotes = "\u201cQuoted text\u201d here"
    cleaned = clean_text_for_tts(text_with_quotes)
    assert "\u201c" not in cleaned
    assert "\u201d" not in cleaned
    assert '"Quoted text" here' in cleaned

    # Test mojibake fix - UTF-8 bytes decoded as Latin-1
    # â€™ is what you get when UTF-8 bytes for ' (curly apostrophe) are decoded as Latin-1
    text_with_mojibake = "Companyâ\x80\x99s didn\xe2\x80\x99t work"
    cleaned = clean_text_for_tts(text_with_mojibake)
    assert "Company's" in cleaned or "Company'" in cleaned  # Should fix to proper apostrophe
    assert "didn't" in cleaned or "didn'" in cleaned
    assert "\x80" not in cleaned
    assert "\x99" not in cleaned


def test_html2text_cleans_nbsp_entities():
    """Test that HTML entities like &nbsp; are properly cleaned for TTS."""
    html_with_nbsp = "<p>This&nbsp;has&nbsp;nbsp&nbsp;entities.</p>"
    result = html2text(html_with_nbsp)

    # Should not contain the Unicode non-breaking space character
    assert "\xa0" not in result
    # Should contain the actual text with regular spaces
    assert "This has nbsp entities" in result


def test_preprocess_html_strips_non_content():
    """Test that preprocess_html strips comments, footers, recommended articles, etc."""
    html = """
    <html>
    <body>
        <article>
            <div class="body markup"><p>This is the real article content.</p></div>
            <div class="comments-section"><p>User comment here</p></div>
            <div class="subscription-widget"><p>Subscribe now!</p></div>
            <footer><p>Copyright 2026</p></footer>
            <div class="portable-archive"><a>Recommended Article 1</a><a>Recommended Article 2</a></div>
            <div class="post-ufi-button">Like</div>
        </article>
        <nav><a>Home</a></nav>
    </body>
    </html>
    """
    result = preprocess_html(html)
    assert "real article content" in result
    assert "User comment" not in result
    assert "Subscribe now" not in result
    assert "Copyright" not in result
    assert "Recommended Article" not in result
    assert "Like" not in result
    assert "Home" not in result


def test_preprocess_html_strips_gmail_chrome():
    """Test that Gmail print-view chrome is stripped."""
    html = """
    <html><body>
    <div class="bodycontainer">
        <table><tr><td>Derek Parks &lt;dnparks@gmail.com&gt;</td></tr></table>
        <hr>
        <div class="maincontent">
            <table><tr><td>Money Stuff: Be Liquid<br>1 message</td></tr></table>
            <hr>
            <table class="message"><tbody><tr><td>
                <font>Matt Levine &lt;noreply@news.bloomberg.com&gt;</font>
                <div>The actual newsletter content goes here.</div>
            </td></tr></tbody></table>
        </div>
    </div>
    </body></html>
    """
    result = preprocess_html(html)
    assert "actual newsletter content" in result
    # User email table and subject table are stripped
    assert "Derek Parks" not in result
    assert "1 message" not in result
    # Sender font tag is stripped
    assert "noreply@news.bloomberg.com" not in result


def test_clean_text_for_tts_strips_email_addresses():
    """Test that email addresses are removed from TTS text."""
    text = "Contact us at support@example.com for help. Written by author@blog.org."
    cleaned = clean_text_for_tts(text)
    assert "support@example.com" not in cleaned
    assert "author@blog.org" not in cleaned
    assert "Contact us at" in cleaned


def test_clean_text_for_tts_strips_newsletter_boilerplate():
    """Test that newsletter boilerplate lines are removed."""
    text = "Great article content here.\nUnsubscribe from this list\nView in browser\nMore content."
    cleaned = clean_text_for_tts(text)
    assert "Great article content" in cleaned
    assert "More content" in cleaned
    assert "Unsubscribe" not in cleaned
    assert "View in browser" not in cleaned


def test_clean_text_for_tts_strips_table_separators():
    """Test that markdown table separators are cleaned up."""
    text = "Some text | --- | --- | --- | more text"
    cleaned = clean_text_for_tts(text)
    assert "| --- |" not in cleaned
    assert "Some text" in cleaned


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

    # Verify asset was fetched (precrawledArchiveAssetId is preferred over contentAssetId)
    mock_fetch_asset.assert_called_once_with("91adcf83-bc10-4a44-87ea-893f60e57bd0")

    # Verify newspaper was called with the HTML content
    mock_newspaper.assert_called_once()
    call_args = mock_newspaper.call_args
    assert call_args[0][0] == "https://example.com/article"  # URL argument
    assert call_args[1]["html"] == "<html><body>Full SingleFile article content here</body></html>"  # html kwarg


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
