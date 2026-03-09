import re
import unicodedata

import ftfy
import newspaper
import requests
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

from hoarderpod.utils import horder_dt_to_py
from hoarderpod.config import Config

markdownify_options = {
    "strip": ["script", "style", "meta", "a", "img", "strong", "template", "svg", "noscript"],  # Remove unwanted elements
    "heading_style": "ATX",  # Use # for headings
    "bullets": "*",  # Consistent bullet points
    "convert_links": "text",  # Only keep link text
    "remove_empty_lines": True,  # Keep empty lines
    "wrap": False,  # Prevent line breaks
    "strip_emphasis": True,
}


class IgnorgeBoldsConverter(MarkdownConverter):
    """
    Create a custom MarkdownConverter that ignores bolds
    """

    def convert_hr(self, el, text, convert_as_inline):
        return "\n"

    def convert_caption(self, el, text, convert_as_inline):
        return "Caption:" + super.convert_caption(el, text, convert_as_inline)

    def convert_list(self, el, text, convert_as_inline):
        return "List:" + super.convert_list(el, text, convert_as_inline)


# Create shorthand method for conversion
def md(html, **options):
    return IgnorgeBoldsConverter(**options).convert(html)


def transform_markdown(text):
    """Transform markdown text to spoken ques.

    Args:
        text: The markdown text to transform

    Returns:
        str: The transformed text
    """
    # Replace h1 headers (# Header)
    text = re.sub(r"^# (.+)$", r"Headline: \1", text, flags=re.MULTILINE)

    # Replace h2-h6 headers (## Header, ### Header, etc)
    text = re.sub(r"^#{2,6} (.+)$", r"Section: \1", text, flags=re.MULTILINE)

    # Replace italics (*text*) but not list items
    # First we split into lines to handle each line separately
    lines = text.split("\n")
    processed_lines = []

    for line in lines:
        # Skip list items (lines starting with * after optional whitespace)
        if re.match(r"^\s*\*\s", line):
            processed_lines.append(line)
        else:
            # Process italics in non-list lines
            line = re.sub(r"\*([^\*]+)\*", r"italic: \1", line)
            processed_lines.append(line)

    return "\n".join(processed_lines)


def parse_with_newspaper(url: str, html: str | None = None) -> dict:
    """Parse article content using newspaper4k.

    Args:
        url: The URL to parse
        html: Optional HTML content to parse instead of downloading from URL

    Returns:
        dict: Dictionary containing parsed authors, title, text and description
    """
    try:
        article = newspaper.Article(url)
        if html:
            # If HTML is provided, set it directly and parse
            article.html = html
            article.is_downloaded = True
        else:
            article.download()
        article.parse()
        return {
            "authors": article.authors,
            "title": article.title,
            "text": article.text,
            "description": article.meta_description,
        }
    except Exception as e:
        print(f"Error parsing article {url}: {e} with newspaper4k")
        return {"authors": [], "title": None, "text": None, "description": None}


def clean_text_for_tts(text: str) -> str:
    """Clean text to remove characters that cause issues with TTS.

    Fixes mojibake (encoding errors), then uses Unicode normalization (NFKC) to
    systematically handle most compatibility characters, plus targeted replacements
    for punctuation that affects TTS.

    Args:
        text: The text to clean

    Returns:
        str: The cleaned text safe for TTS
    """
    # Step 0: Fix mojibake (encoding errors like â€™ → ')
    # This handles cases where UTF-8 bytes were decoded as Latin-1
    text = ftfy.fix_text(text)

    # Step 1: NFKC normalization handles compatibility characters automatically
    # This converts: non-breaking spaces, full-width characters, ligatures, etc.
    text = unicodedata.normalize('NFKC', text)

    # Step 2: Handle punctuation and special characters that NFKC doesn't normalize
    # Replace various quotation marks and problematic characters with ASCII equivalents
    quote_replacements = {
        '\u2018': "'",  # ' left single quotation mark
        '\u2019': "'",  # ' right single quotation mark (curly apostrophe)
        '\u201a': "'",  # ‚ single low-9 quotation mark
        '\u201b': "'",  # ‛ single high-reversed-9 quotation mark
        '\u201c': '"',  # " left double quotation mark
        '\u201d': '"',  # " right double quotation mark
        '\u201e': '"',  # „ double low-9 quotation mark
        '\u201f': '"',  # ‟ double high-reversed-9 quotation mark
        '\u2032': "'",  # ′ prime
        '\u2033': '"',  # ″ double prime
        '\u2013': '-',  # – en dash
        '\u2014': '-',  # — em dash
        '\u200b': '',   # zero-width space (remove)
    }

    for unicode_char, ascii_char in quote_replacements.items():
        text = text.replace(unicode_char, ascii_char)

    # Step 3: Remove email addresses (privacy + TTS noise)
    text = re.sub(r'\S+@\S+\.\S+', '', text)

    # Step 4: Remove common newsletter/email boilerplate lines
    text = re.sub(r'^.*(?:Unsubscribe|View in browser|Reply-To:|You received this message because).*$',
                  '', text, flags=re.MULTILINE | re.IGNORECASE)

    # Step 5: Clean up markdown table separators (| --- | --- | ...)
    text = re.sub(r'(\|\s*---\s*)+\|?', '', text)

    # Step 6: Collapse multiple spaces and blank lines
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text


# Classes/IDs that indicate non-article content to strip before TTS
_STRIP_CLASS_PATTERNS = re.compile(
    r'comment|footer|sidebar|related|recommend|subscription|subscribe|'
    r'portable-archive|navigation|share-dialog|social-share|post-ufi|'
    r'restack|like-button|pencraft.*footer',
    re.IGNORECASE,
)


def _strip_gmail_chrome(soup: BeautifulSoup) -> None:
    """Strip Gmail print-view chrome (email headers, user info) from the soup.

    Detects Gmail print layout by looking for the 'maincontent' class and
    'table.message' structure. Removes the user's email display, subject line
    table, and email header rows (From, To, Date, Reply-To).
    """
    maincontent = soup.find(class_='maincontent')
    if not maincontent:
        return

    # Remove the user email table above maincontent (inside bodycontainer)
    bodycontainer = soup.find(class_='bodycontainer')
    if bodycontainer:
        for table in bodycontainer.find_all('table', recursive=False):
            if table != maincontent and maincontent not in table.descendants:
                table.decompose()

    # Remove the subject line table inside maincontent (before the message table)
    msg_table = maincontent.find('table', class_='message')
    if msg_table:
        for table in maincontent.find_all('table', recursive=False):
            if table != msg_table:
                table.decompose()

        # Inside the message, strip sender <font> tags (contain "Name <email>")
        for font in msg_table.find_all('font', recursive=True):
            text = font.get_text()
            if re.search(r'<[^>]*@[^>]*>', text):
                font.decompose()


def preprocess_html(html: str) -> str:
    """Remove problematic HTML elements before markdown conversion.

    Strips scripts, styles, templates, SVGs, and non-article sections like
    comments, footers, recommended articles, subscription widgets, and
    Gmail print-view chrome.

    Args:
        html: The raw HTML to preprocess

    Returns:
        str: HTML with problematic elements removed
    """
    # Step 1: Fast regex removal for elements that are always noise
    html = re.sub(r'<template[^>]*>.*?</template>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<svg[^>]*>.*?</svg>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Step 2: Use BeautifulSoup to remove non-article sections
    soup = BeautifulSoup(html, 'html.parser')

    # Strip Gmail print-view chrome if detected
    _strip_gmail_chrome(soup)

    # Remove semantic HTML5 elements that aren't article content
    for tag_name in ['footer', 'nav', 'aside']:
        for el in soup.find_all(tag_name):
            el.decompose()

    # Remove elements whose class matches non-content patterns
    for el in soup.find_all(class_=_STRIP_CLASS_PATTERNS):
        el.decompose()

    return str(soup)


def html2text(html: str) -> str:
    """Convert HTML to text using markdownify.

    Args:
        html: The HTML to convert

    Returns:
        str: The text converted from the HTML
    """
    # Pre-process to remove problematic elements
    html = preprocess_html(html)

    markdown = md(html, **markdownify_options)
    transformed = transform_markdown(markdown)
    return clean_text_for_tts(transformed)


def fetch_asset_content(asset_id: str) -> str | None:
    """Fetch HTML content from Hoarder asset API.

    Args:
        asset_id: The asset ID to fetch

    Returns:
        str: The HTML content from the asset, or None if fetch fails
    """
    try:
        url = f"{Config.HOARDER_ROOT_URL}/api/v1/assets/{asset_id}"
        headers = {
            "Authorization": f"Bearer {Config.HOARDER_API_KEY}",
            "Content-Type": "application/json",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching asset {asset_id}: {e}")
        return None


def get_episode_dict(bookmark: dict) -> dict:
    """Get the episode dict including text, title, description, and authors of a bookmark.

    Args:
        bookmark: The bookmark dict from Hoarder

    Returns:
        dict: The episode dict including text, title, description, and authors of the bookmark
    """
    content = bookmark["content"]
    url = content["url"]

    # Get HTML content - either from inline htmlContent or from asset
    html_content = content.get("htmlContent")
    if not html_content:
        # For SingleFile articles, content is stored as an asset
        # Try precrawledArchiveAssetId first (full page), then contentAssetId
        asset_id = content.get("precrawledArchiveAssetId") or content.get("contentAssetId")
        if asset_id:
            print(f"Fetching asset content for bookmark {bookmark['id']}, asset {asset_id}")
            html_content = fetch_asset_content(asset_id)

    # Try newspaper extraction - if we have HTML content from asset, use it; otherwise download from URL
    newspaper_data = parse_with_newspaper(url, html=html_content if html_content else None)

    # Fall back to our HTML-to-text conversion if newspaper fails
    html2text_text = html2text(html_content) if html_content else ""

    # todo - use llm to describe images see ImageBlockConverter

    if newspaper_data["text"] is None or len(html2text_text.split()) > len(newspaper_data["text"].split()):
        text = html2text_text
    else:
        # Clean newspaper text for TTS (handles curly quotes, Unicode spaces, etc.)
        text = clean_text_for_tts(newspaper_data["text"])

    if newspaper_data["title"] is None or len(content["title"]) > len(newspaper_data["title"]):
        title = content["title"]
    else:
        title = newspaper_data["title"]

    if newspaper_data["description"] is None and content["description"] is None:
        description = ""
    elif newspaper_data["description"] is None:
        description = content["description"]
    elif content["description"] is None:
        description = newspaper_data["description"]
    elif len(content["description"]) > len(newspaper_data["description"]):
        description = content["description"]
    else:
        description = newspaper_data["description"]

    return {
        "id": bookmark["id"],
        "title": title,
        "description": description,
        "text": text,
        "authors": newspaper_data["authors"],
        "url": url,
        "createdAt": horder_dt_to_py(bookmark["createdAt"]),
        "crawledAt": horder_dt_to_py(bookmark["content"]["crawledAt"]),
    }
