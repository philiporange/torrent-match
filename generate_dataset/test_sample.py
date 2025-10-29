"""
Minimal test suite for sample.py torrent sampling functionality.

Run with: pytest test_sample.py
"""

import pytest
from sample import parse_ratio, compute_sample_id


class TestParseRatio:
    """Test ratio string parsing and normalization."""

    def test_decimal_ratio(self):
        """Test parsing decimal ratios."""
        tv_ratio, movie_ratio = parse_ratio("0.6:0.4")
        assert abs(tv_ratio - 0.6) < 0.001
        assert abs(movie_ratio - 0.4) < 0.001
        assert abs(tv_ratio + movie_ratio - 1.0) < 0.001

    def test_integer_ratio(self):
        """Test parsing integer ratios."""
        tv_ratio, movie_ratio = parse_ratio("4:3")
        assert abs(tv_ratio - 4/7) < 0.001
        assert abs(movie_ratio - 3/7) < 0.001

    def test_equal_ratio(self):
        """Test 1:1 ratio normalization."""
        tv_ratio, movie_ratio = parse_ratio("1:1")
        assert tv_ratio == 0.5
        assert movie_ratio == 0.5

    def test_large_numbers(self):
        """Test ratio with large numbers."""
        tv_ratio, movie_ratio = parse_ratio("100:50")
        assert abs(tv_ratio - 2/3) < 0.001
        assert abs(movie_ratio - 1/3) < 0.001

    def test_invalid_format_missing_colon(self):
        """Test error on missing colon."""
        with pytest.raises(ValueError, match="Invalid ratio format"):
            parse_ratio("0.6")

    def test_invalid_format_too_many_parts(self):
        """Test error on too many parts."""
        with pytest.raises(ValueError, match="Invalid ratio format"):
            parse_ratio("1:2:3")

    def test_invalid_non_numeric(self):
        """Test error on non-numeric values."""
        with pytest.raises(ValueError, match="must be numeric"):
            parse_ratio("abc:def")

    def test_invalid_zero_value(self):
        """Test error on zero values."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_ratio("0:1")

    def test_invalid_negative_value(self):
        """Test error on negative values."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_ratio("1:-1")


class TestComputeSampleId:
    """Test sample ID hash generation."""

    def test_deterministic_hash(self):
        """Test that the same sample produces the same hash."""
        sample = {
            "name": "Test.Torrent.S01E01.mkv",
            "size": 1000000,
            "imdb_id": "tt1234567",
            "type": "tv",
            "files": [{"path": "test.mkv", "size": 1000000}],
        }
        hash1 = compute_sample_id(sample)
        hash2 = compute_sample_id(sample)
        assert hash1 == hash2

    def test_hash_length(self):
        """Test that hash is 16 characters."""
        sample = {
            "name": "Test",
            "size": 100,
            "imdb_id": None,
            "type": "movie",
            "files": [],
        }
        sample_id = compute_sample_id(sample)
        assert len(sample_id) == 16

    def test_different_samples_different_hashes(self):
        """Test that different samples produce different hashes."""
        sample1 = {
            "name": "Movie.A.2020.mkv",
            "size": 1000000,
            "imdb_id": "tt1111111",
            "type": "movie",
            "files": [],
        }
        sample2 = {
            "name": "Movie.B.2020.mkv",
            "size": 1000000,
            "imdb_id": "tt2222222",
            "type": "movie",
            "files": [],
        }
        assert compute_sample_id(sample1) != compute_sample_id(sample2)

    def test_hash_is_hexadecimal(self):
        """Test that hash contains only hexadecimal characters."""
        sample = {
            "name": "Test",
            "size": 100,
            "imdb_id": None,
            "type": "tv",
            "files": [],
        }
        sample_id = compute_sample_id(sample)
        assert all(c in "0123456789abcdef" for c in sample_id)

    def test_order_independence(self):
        """Test that dict key order doesn't affect hash (due to sort_keys)."""
        # Create samples with same data but different key order
        sample1 = {
            "name": "Test",
            "size": 100,
            "imdb_id": "tt123",
            "type": "movie",
            "files": [],
        }
        # Python dicts maintain insertion order, but JSON sorting handles this
        sample2 = {
            "files": [],
            "type": "movie",
            "imdb_id": "tt123",
            "size": 100,
            "name": "Test",
        }
        assert compute_sample_id(sample1) == compute_sample_id(sample2)

    def test_null_imdb_id(self):
        """Test hash generation with null IMDB ID."""
        sample = {
            "name": "Test",
            "size": 100,
            "imdb_id": None,
            "type": "tv",
            "files": [],
        }
        sample_id = compute_sample_id(sample)
        assert len(sample_id) == 16
        assert isinstance(sample_id, str)

    def test_empty_files_list(self):
        """Test hash generation with empty files list."""
        sample = {
            "name": "Test",
            "size": 100,
            "imdb_id": "tt123",
            "type": "movie",
            "files": [],
        }
        sample_id = compute_sample_id(sample)
        assert len(sample_id) == 16

    def test_multiple_files(self):
        """Test hash generation with multiple files."""
        sample = {
            "name": "Test",
            "size": 2000,
            "imdb_id": "tt123",
            "type": "tv",
            "files": [
                {"path": "file1.mkv", "size": 1000},
                {"path": "file2.srt", "size": 1000},
            ],
        }
        sample_id = compute_sample_id(sample)
        assert len(sample_id) == 16


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
