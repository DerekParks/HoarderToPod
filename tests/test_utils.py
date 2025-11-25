import pytest
from datetime import datetime, timezone

from hoarderpod.utils import oxford_join, to_local_datetime, to_utc, horder_dt_to_py, remove_www, sanitize_xml_string


def test_remove_www():
    # Test with www prefix
    assert remove_www("www.example.com") == "example.com"
    
    # Test without www prefix
    assert remove_www("example.com") == "example.com"
    
    # Test with other prefix
    assert remove_www("sub.example.com") == "sub.example.com"
    
    # Test with empty string
    assert remove_www("") == ""
    
    # Test with just www
    assert remove_www("www.") == ""


def test_sanitize_xml_string():
    # Handles None and empty strings
    assert sanitize_xml_string(None) == ""
    assert sanitize_xml_string("") == ""
    
    # Normal text passes through unchanged
    assert sanitize_xml_string("Hello World") == "Hello World"
    
    # Removes NULL bytes
    assert sanitize_xml_string("Hello\x00World") == "HelloWorld"
    
    # Keeps valid whitespace (tab, newline, carriage return)
    assert sanitize_xml_string("Hello\t\nWorld") == "Hello\t\nWorld"
    
    # Replaces invalid control characters with spaces
    assert sanitize_xml_string("Hello\x01World") == "Hello World"
    
    # Handles mixed valid and invalid characters
    assert sanitize_xml_string("Hello\x00\t\x01\nWorld") == "Hello\t \nWorld"