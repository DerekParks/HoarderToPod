import pytest
from datetime import datetime, timezone

from hoarderpod.utils import oxford_join, to_local_datetime, to_utc, horder_dt_to_py, remove_www


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