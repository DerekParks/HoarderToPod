from hoarderpod.article_parse import transform_markdown


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
