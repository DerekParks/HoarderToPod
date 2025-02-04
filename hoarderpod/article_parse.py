import re

import newspaper
from markdownify import MarkdownConverter

from hoarderpod.utils import horder_dt_to_py

markdownify_options = {
    "strip": ["script", "style", "meta", "a", "img", "strong"],  # Remove unwanted elements
    "heading_style": "ATX",  # Use # for headings
    "bullets": "*",  # Consistent bullet points
    "convert_links": "text",  # Only keep link text
    "remove_empty_lines": True,  # Keep empty lines
    "wrap": True,  # Prevent line breaks
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


def parse_with_newspaper(url: str) -> dict:
    """Parse article content using newspaper4k.

    Args:
        url: The URL to parse

    Returns:
        dict: Dictionary containing parsed authors, title, text and description
    """
    try:
        article = newspaper.Article(url)
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


def html2text(html: str) -> str:
    """Convert HTML to text using markdownify.

    Args:
        html: The HTML to convert

    Returns:
        str: The text converted from the HTML
    """
    return transform_markdown(md(html, **markdownify_options))


def get_episode_dict(bookmark: dict) -> dict:
    """Get the episode dict including text, title, description, and authors of a bookmark.

    Args:
        bookmark: The bookmark dict from Hoarder

    Returns:
        dict: The episode dict including text, title, description, and authors of the bookmark
    """
    content = bookmark["content"]
    url = content["url"]

    newspaper_data = parse_with_newspaper(url)
    html2text_text = html2text(content["htmlContent"]) if content["htmlContent"] else ""

    # todo - use llm to describe images see ImageBlockConverter

    if newspaper_data["text"] is None or len(html2text_text.split()) > len(newspaper_data["text"].split()):
        text = html2text_text
    else:
        text = newspaper_data["text"]

    if newspaper_data["title"] is None or len(content["title"]) > len(newspaper_data["title"]):
        title = content["title"]
    else:
        title = newspaper_data["title"]

    if newspaper_data["description"] is None or len(content["description"]) > len(newspaper_data["description"]):
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
