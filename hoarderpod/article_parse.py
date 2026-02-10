import re
import unicodedata

import ftfy
import newspaper
import requests
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

    # Step 3: Collapse multiple spaces
    text = re.sub(r' +', ' ', text)

    return text


def preprocess_html(html: str) -> str:
    """Remove problematic HTML elements before markdown conversion.

    Args:
        html: The raw HTML to preprocess

    Returns:
        str: HTML with problematic elements removed
    """
    # Remove template tags and their contents (which often contain CSS/JS)
    html = re.sub(r'<template[^>]*>.*?</template>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove style tags and their contents
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove script tags and their contents
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove SVG tags and their contents
    html = re.sub(r'<svg[^>]*>.*?</svg>', '', html, flags=re.DOTALL | re.IGNORECASE)

    return html


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
