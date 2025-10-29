"""
Core matching functionality for torrent content identification.

This module provides a simplified API for matching torrent names, file lists,
or full `.torrent` files to their corresponding media content (movies/TV
shows). It wraps the lower-level detector orchestration with convenience
utilities tailored for common usage patterns.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple

# Import from parent torrent_detector module
from torrent_detector import (
    TorrentContentDetector,
    MediaType,
    ConfidenceLevel,
    MediaIdentification,
    DatasetSample,
    FileStructureDetector,
    EpisodeExtractor,
    TMDBEnricher,
    create_tmdb_enricher,
    set_verbose,
    is_verbose,
    vprint,
    init_from_env,
)
from .torrent_file_parser import (
    ParsedTorrent,
    TorrentFileParsingError,
    parse_torrent_file,
)


# Re-export for convenience
__all__ = [
    'match',
    'match_batch',
    'match_from_sample',
    'match_torrent_file',
    'TorrentMatcher',
    'TorrentContentDetector',
    'MediaType',
    'ConfidenceLevel',
    'MediaIdentification',
    'DatasetSample',
    'FileStructureDetector',
    'EpisodeExtractor',
    'TMDBEnricher',
    'ParsedTorrent',
    'TorrentFileParsingError',
    'parse_torrent_file',
    'set_verbose',
    'init_from_env',
]


class TorrentMatcher:
    """
    High-level interface for torrent content matching.

    This class provides a simplified API for common matching operations
    with sensible defaults and automatic configuration from environment variables.

    Examples:
        >>> matcher = TorrentMatcher()
        >>> result = matcher.match("The.Matrix.1999.1080p.BluRay.x264")
        >>> print(result.title, result.year, result.imdb_id)

        >>> # Batch matching
        >>> results = matcher.match_batch([
        ...     "Movie.Name.2023.1080p",
        ...     "TV.Show.S01E01.720p"
        ... ])
    """

    def __init__(
        self,
        tmdb_api_key: Optional[str] = None,
        enable_enricher: bool = False,
        use_llm_fallback: bool = False,
        llm_api_key: Optional[str] = None,
        llm_api_endpoint: Optional[str] = None,
        llm_model: Optional[str] = None,
        cache_db_path: Optional[str] = None,
        enricher_cache_path: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Initialize the matcher with optional configuration.

        Args:
            tmdb_api_key: TMDB API key (falls back to TMDB_API_KEY env var)
            enable_enricher: Enable TMDB enricher for detailed metadata
            use_llm_fallback: Use LLM parser as fallback
            llm_api_key: LLM API key (falls back to LLM_API_KEY env var)
            llm_api_endpoint: LLM API endpoint (falls back to LLM_API_ENDPOINT env var)
            llm_model: LLM model name (falls back to LLM_MODEL env var)
            cache_db_path: Path to cache database
            enricher_cache_path: Path to enricher cache database
            verbose: Enable verbose logging
        """
        # Initialize verbose mode
        if verbose:
            set_verbose(True)
        else:
            init_from_env()

        # Get configuration from environment if not provided
        tmdb_api_key = tmdb_api_key or os.getenv('TMDB_API_KEY')
        llm_api_key = llm_api_key or os.getenv('LLM_API_KEY')
        llm_api_endpoint = llm_api_endpoint or os.getenv('LLM_API_ENDPOINT')
        llm_model = llm_model or os.getenv('LLM_MODEL')

        # Use LLM fallback if env var is set
        if os.getenv('USE_LLM_FALLBACK', '').lower() in ('1', 'true', 'yes', 'on'):
            use_llm_fallback = True

        # Initialize detector
        self.detector = TorrentContentDetector(
            tmdb_api_key=tmdb_api_key,
            llm_api_key=llm_api_key if use_llm_fallback else None,
            llm_api_endpoint=llm_api_endpoint if use_llm_fallback else None,
            llm_model=llm_model if use_llm_fallback else None,
            cache_db_path=cache_db_path or "/tmp/torrent_match_cache.db",
            use_llm_fallback=use_llm_fallback,
            enable_caching=True,
            enable_enricher=enable_enricher,
            enricher_cache_path=enricher_cache_path or "/tmp/torrent_match/tmdb.sqlite",
        )

    def match(
        self,
        torrent_name: str,
        files: Optional[Union[List[str], List[Dict[str, Any]]]] = None,
        detail: bool = False,
    ) -> Union[MediaIdentification, Dict[str, Any]]:
        """
        Match a single torrent to its media content.

        Args:
            torrent_name: The torrent name to match
            files: Optional list of file paths or file info dicts
            detail: Return detailed output dict instead of MediaIdentification object

        Returns:
            MediaIdentification object or dict with match results

        Examples:
            >>> result = matcher.match("The.Matrix.1999.1080p")
            >>> print(result.title)  # "The Matrix"

            >>> # With files
            >>> result = matcher.match(
            ...     "Breaking.Bad.S05E14.720p",
            ...     files=["Breaking.Bad.S05E14.mkv"]
            ... )

            >>> # Detailed output
            >>> output = matcher.match("Inception.2010", detail=True)
            >>> print(output['detail']['genres'])
        """
        identification = self.detector.identify(torrent_name, files)

        if detail:
            return identification.to_dict(detail=True)
        return identification

    def match_torrent_file(
        self,
        torrent_file: Union[str, os.PathLike, Path],
        detail: bool = False,
    ) -> Union[MediaIdentification, Dict[str, Any]]:
        """
        Match a torrent by inspecting the `.torrent` file contents.

        Args:
            torrent_file: Path to the torrent file.
            detail: Return detailed output dict instead of MediaIdentification.

        Returns:
            MediaIdentification object or dict with match results.
        """
        parsed = parse_torrent_file(torrent_file)
        return self.match(parsed.name, parsed.files, detail=detail)

    def match_batch(
        self,
        torrents: Union[List[str], List[Tuple[str, Optional[List]]]],
        max_workers: int = 5,
        show_progress: bool = True,
        detail: bool = False,
    ) -> List[Union[MediaIdentification, Dict[str, Any]]]:
        """
        Match multiple torrents in parallel.

        Args:
            torrents: List of torrent names or (name, files) tuples
            max_workers: Maximum parallel workers
            show_progress: Show progress during processing
            detail: Return detailed output dicts

        Returns:
            List of MediaIdentification objects or dicts

        Examples:
            >>> results = matcher.match_batch([
            ...     "Movie.Name.2023.1080p",
            ...     "TV.Show.S01E01.720p"
            ... ])

            >>> # With files
            >>> results = matcher.match_batch([
            ...     ("Movie.2023", ["movie.mkv"]),
            ...     ("Show.S01E01", ["episode.mkv"])
            ... ])
        """
        # Normalize input to (name, files) tuples
        if torrents and isinstance(torrents[0], str):
            torrents = [(name, None) for name in torrents]

        identifications = self.detector.identify_batch(
            torrents,
            max_workers=max_workers,
            show_progress=show_progress
        )

        if detail:
            return [ident.to_dict(detail=True) for ident in identifications]
        return identifications

    def match_from_sample(
        self,
        sample: DatasetSample,
        detail: bool = False,
    ) -> Union[MediaIdentification, Dict[str, Any]]:
        """
        Match from a DatasetSample object.

        Args:
            sample: DatasetSample with torrent information
            detail: Return detailed output dict

        Returns:
            MediaIdentification object or dict
        """
        identification = self.detector.identify_from_sample(sample)

        if detail:
            return identification.to_dict(detail=True)
        return identification


# Convenience functions using a default matcher instance
_default_matcher: Optional[TorrentMatcher] = None


def _get_default_matcher() -> TorrentMatcher:
    """Get or create the default matcher instance."""
    global _default_matcher
    if _default_matcher is None:
        _default_matcher = TorrentMatcher()
    return _default_matcher


def match(
    torrent_name: str,
    files: Optional[Union[List[str], List[Dict[str, Any]]]] = None,
    detail: bool = False,
) -> Union[MediaIdentification, Dict[str, Any]]:
    """
    Match a single torrent using the default matcher.

    This is a convenience function that uses a shared TorrentMatcher instance.

    Args:
        torrent_name: The torrent name to match
        files: Optional list of file paths or file info dicts
        detail: Return detailed output dict

    Returns:
        MediaIdentification object or dict

    Examples:
        >>> from torrent_match import match
        >>> result = match("The.Matrix.1999.1080p")
        >>> print(result.title, result.year)
    """
    matcher = _get_default_matcher()
    return matcher.match(torrent_name, files, detail)


def match_batch(
    torrents: Union[List[str], List[Tuple[str, Optional[List]]]],
    max_workers: int = 5,
    show_progress: bool = True,
    detail: bool = False,
) -> List[Union[MediaIdentification, Dict[str, Any]]]:
    """
    Match multiple torrents using the default matcher.

    Args:
        torrents: List of torrent names or (name, files) tuples
        max_workers: Maximum parallel workers
        show_progress: Show progress
        detail: Return detailed output dicts

    Returns:
        List of MediaIdentification objects or dicts

    Examples:
        >>> from torrent_match import match_batch
        >>> results = match_batch([
        ...     "Movie.Name.2023.1080p",
        ...     "TV.Show.S01E01.720p"
        ... ])
    """
    matcher = _get_default_matcher()
    return matcher.match_batch(torrents, max_workers, show_progress, detail)


def match_from_sample(
    sample: DatasetSample,
    detail: bool = False,
) -> Union[MediaIdentification, Dict[str, Any]]:
    """
    Match from a DatasetSample using the default matcher.

    Args:
        sample: DatasetSample with torrent information
        detail: Return detailed output dict

    Returns:
        MediaIdentification object or dict
    """
    matcher = _get_default_matcher()
    return matcher.match_from_sample(sample, detail)


def match_torrent_file(
    torrent_file: Union[str, os.PathLike, Path],
    detail: bool = False,
) -> Union[MediaIdentification, Dict[str, Any]]:
    """
    Match a torrent by providing the `.torrent` file path.

    Args:
        torrent_file: Path to the torrent file.
        detail: Return detailed output dict.

    Returns:
        MediaIdentification object or dict.
    """
    matcher = _get_default_matcher()
    return matcher.match_torrent_file(torrent_file, detail)
