"""
Torrent Content Detector Module

A robust Python module for identifying media content (movies/TV shows) from torrent names
and file structures, using multiple parsing strategies with progressive fallback mechanisms.

This module is designed to work with torrent metadata datasets containing torrent names,
file listings, and IMDB identifiers.
"""

from .models import (
    MediaType,
    ConfidenceLevel,
    ParseResult,
    TorrentContent,
    MediaIdentification,
    DatasetSample
)
from .detector import TorrentContentDetector
from .file_structure_detector import FileStructureDetector
from .episode_extractor import EpisodeExtractor
from .verbose import set_verbose, is_verbose, vprint, init_from_env
from .tmdb_enricher import TMDBEnricher, create_tmdb_enricher

__version__ = "0.1.0"
__author__ = "Philip Orange <git@philiporange.com>"

__all__ = [
    'MediaType',
    'ConfidenceLevel',
    'ParseResult',
    'TorrentContent',
    'MediaIdentification',
    'DatasetSample',
    'TorrentContentDetector',
    'FileStructureDetector',
    'EpisodeExtractor',
    'TMDBEnricher',
    'create_tmdb_enricher',
    'set_verbose',
    'is_verbose',
    'vprint',
    'init_from_env'
]