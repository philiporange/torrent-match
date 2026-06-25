"""
Tests for torrent matching logic.

These tests validate that torrent names and files are correctly matched to
their TMDB entries, with correct title extraction and IMDB ID retrieval.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from torrent_detector.detector import TorrentContentDetector
from torrent_detector.models import MediaType, ConfidenceLevel


class TestTitlePreservation:
    """
    Test that TMDB-validated titles are preserved and not overwritten
    by parser consensus titles.

    These tests guard against regression of the bug where parser consensus
    would overwrite correct TMDB titles with incorrect parsed titles.
    """

    @pytest.fixture
    def detector(self):
        """Create detector with TMDB API key from environment."""
        import os
        api_key = os.environ.get('TMDB_API_KEY')
        if not api_key:
            pytest.skip("TMDB_API_KEY not set")
        return TorrentContentDetector(tmdb_api_key=api_key)

    def test_dark_knight_title_preserved(self, detector):
        """
        Test that 'The Dark Knight' is correctly identified even when
        the torrent name contains 'Batman' prefix.

        Regression test: Previously, parser consensus would return
        'Batman The Dark Knight' which overwrote the correct TMDB title.
        """
        # The torrent internal name has 'Batman' prefix but TMDB knows
        # the correct title is 'The Dark Knight'
        result = detector.identify("Batman The Dark Knight (2008) [1080p]")

        assert result.tmdb_match is True
        assert result.title == "The Dark Knight"
        assert result.imdb_id == "tt0468569"
        assert result.year == 2008
        assert result.media_type == MediaType.MOVIE

    def test_wall_e_title_preserved(self, detector):
        """
        Test that 'WALL-E' matches correctly with special character handling.

        The official title uses an interpunct (·) but torrents often use
        hyphen (-) or space. TMDB should find the correct match.
        """
        result = detector.identify("WALL-E (2008) [1080p]")

        assert result.tmdb_match is True
        # TMDB returns "WALL·E" with interpunct
        assert "WALL" in result.title
        assert result.imdb_id == "tt0910970"
        assert result.year == 2008
        assert result.media_type == MediaType.MOVIE

    def test_wall_e_with_space(self, detector):
        """Test WALL E with space instead of hyphen."""
        result = detector.identify("WALL E (2008) [1080p]")

        assert result.tmdb_match is True
        assert "WALL" in result.title
        assert result.imdb_id == "tt0910970"

    def test_tmdb_title_preserved_over_parser_consensus(self, detector):
        """
        Verify that when TMDB match succeeds, its title is preserved
        regardless of what parser consensus suggests.

        Using The Matrix as a reliable test case - parsers might extract
        different variations but TMDB should return the canonical title.
        """
        result = detector.identify("The.Matrix.1999.1080p.BluRay.x264")

        assert result.tmdb_match is True
        assert result.title == "The Matrix"
        assert result.imdb_id == "tt0133093"


class TestBasicMatching:
    """Basic matching tests for common cases."""

    @pytest.fixture
    def detector(self):
        import os
        api_key = os.environ.get('TMDB_API_KEY')
        if not api_key:
            pytest.skip("TMDB_API_KEY not set")
        return TorrentContentDetector(tmdb_api_key=api_key)

    def test_simple_movie_match(self, detector):
        """Test a straightforward movie match."""
        result = detector.identify("The Matrix (1999) [1080p] [BluRay]")

        assert result.tmdb_match is True
        assert result.title == "The Matrix"
        assert result.imdb_id == "tt0133093"
        assert result.year == 1999

    def test_movie_with_quality_suffix(self, detector):
        """Test movie name with quality indicators."""
        result = detector.identify("Inception.2010.1080p.BluRay.x264-SPARKS")

        assert result.tmdb_match is True
        assert result.title == "Inception"
        assert result.year == 2010


class TestParserConsensusWithoutTMDB:
    """Test parser consensus when TMDB validation is not available."""

    @pytest.fixture
    def detector_no_tmdb(self):
        """Create detector without TMDB."""
        return TorrentContentDetector()

    def test_consensus_used_without_tmdb(self, detector_no_tmdb):
        """When TMDB is unavailable, parser consensus title should be used."""
        result = detector_no_tmdb.identify("Some.Movie.2020.1080p.WEB-DL")

        # Without TMDB, parser consensus is used
        assert result.tmdb_match is False
        assert result.title is not None
        assert "Movie" in result.title or "Some" in result.title
