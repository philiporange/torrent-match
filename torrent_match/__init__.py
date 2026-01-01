"""
Torrent Match - Media identification for torrents.

A clean API for identifying movies and TV shows from torrent names and file structures.
"""

from .match import (
    # Main matching functions
    match,
    match_batch,
    match_from_sample,
    match_torrent_file,

    # Detector classes
    TorrentMatcher,

    # Re-export from torrent_detector
    TorrentContentDetector,
    MediaType,
    ConfidenceLevel,
    MediaIdentification,
    DatasetSample,
    FileStructureDetector,
    EpisodeExtractor,
    TMDBEnricher,

    # Utilities
    ParsedTorrent,
    TorrentFileParsingError,
    parse_torrent_file,
    set_verbose,
    init_from_env,
)

__version__ = "0.1.0"

__all__ = [
    # Main functions
    'match',
    'match_batch',
    'match_from_sample',
    'match_torrent_file',

    # Classes
    'TorrentMatcher',
    'TorrentContentDetector',
    'ParsedTorrent',

    # Models
    'MediaType',
    'ConfidenceLevel',
    'MediaIdentification',
    'DatasetSample',

    # Additional classes
    'FileStructureDetector',
    'EpisodeExtractor',
    'TMDBEnricher',
    'TorrentFileParsingError',
    'parse_torrent_file',

    # Utilities
    'set_verbose',
    'init_from_env',
]
