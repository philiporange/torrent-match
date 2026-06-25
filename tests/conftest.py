"""
Pytest configuration and fixtures for torrent_match tests.

This module provides shared fixtures and hooks for test configuration,
including cache management to ensure test isolation.
"""

import os
import pytest


def clear_tmdb_cache():
    """Clear TMDB validation cache files."""
    cache_paths = [
        "/tmp/torrent_interpret.db",
        "/tmp/torrent_interpret.db.settings",
        "/tmp/torrent_match_cache.db",
        "/tmp/torrent_match_cache.db.settings",
    ]
    for path in cache_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


@pytest.fixture(scope="function", autouse=True)
def clear_cache_before_each_test():
    """Clear TMDB validation cache before each test to ensure fresh state."""
    clear_tmdb_cache()
    yield
    # Also clear after to prevent interference with other test modules
    clear_tmdb_cache()
