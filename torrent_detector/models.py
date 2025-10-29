"""
Data models for torrent content detection.

This module defines the core data structures used throughout the torrent detection system.

Media Type Detection:
Media type (movie vs TV) is determined using a hierarchical approach:
1. Torrent name patterns - Definitive indicators (S01E01 = TV episode, dates = TV)
2. File structure analysis - Folder patterns, file sizes, video file counts
3. TMDB dual-type validation - When uncertain, checks both movie and TV, picks best match

Each detection source provides a confidence level, and the system uses the most
confident source, with definitive name patterns (confidence >= 0.95) taking precedence.

Media Types:
- MOVIE: Single movie file
- TV_EPISODE: Single TV episode
- TV_SEASON: Complete season pack
- TV_MULTI_SEASON: Multiple seasons or complete series
- TV_SHOW: General TV show (when not specific)

Medium Field:
The 'medium' property provides a simplified TV/MOVIE classification derived from
the granular media_type. This is required for TMDB lookups and simplifies logic
that only needs to distinguish between movies and TV content.

Confidence Semantics:
The confidence level represents "how sure we are that the detected title is correct,"
based ENTIRELY on weighted parser agreement. Higher confidence means more parsers
(especially high-trust parsers like GuessIt and PTN) agreed on the same title.

Confidence does NOT reflect:
- TMDB match status
- Year accuracy
- Episode/season detection
- File structure analysis

It is purely a measure of title consensus across parsers.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum


class MediaType(Enum):
    """Media type classification"""
    MOVIE = "movie"
    TV_SHOW = "tv_show"  # General TV show (when not specific to episode/season)
    TV_EPISODE = "tv_episode"
    TV_SEASON = "tv_season"
    TV_MULTI_SEASON = "tv_multi_season"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    """
    Confidence levels for title identification.

    These levels represent our certainty that the detected title is correct,
    based purely on weighted parser consensus:

    - HIGH (0.9): Strong parsers (GuessIt, PTN) agree on the title
    - MEDIUM (0.7): Moderate parser agreement, or only weaker parsers agree
    - LOW (0.5): Limited agreement, or only one parser found a title
    - VERY_LOW (0.3): Minimal agreement, or conflicting results

    Note: Parser-provided confidence values are IGNORED. Only inter-parser
    agreement matters.
    """
    HIGH = 0.9
    MEDIUM = 0.7
    LOW = 0.5
    VERY_LOW = 0.3


@dataclass
class ParseResult:
    """
    Result from individual parser.

    Parser-provided confidence has been removed entirely. Final confidence
    is computed by the consensus title confidence system based on parser
    agreement, not individual parser self-assessment.
    """
    title: Optional[str]
    year: Optional[int]
    season: Optional[int]
    episode: Optional[int]
    media_type: MediaType
    quality: Optional[str]
    source: Optional[str]
    codec: Optional[str]
    group: Optional[str]
    parser_name: str
    raw_data: Dict[str, Any]


@dataclass
class TorrentContent:
    """Analyzed torrent content from dataset"""
    torrent_name: str
    files: List[str]
    folder_structure: Dict[str, Any]
    media_type: MediaType
    movie_file_count: int
    has_season_folders: bool
    normalized_name: str

    def __post_init__(self):
        """Ensure files is a list of strings"""
        if isinstance(self.files, list):
            self.files = [str(f) for f in self.files]
        else:
            self.files = []


@dataclass
class MediaIdentification:
    """
    Final identification result.

    Fields:
        imdb_id: IMDB identifier if found via TMDB
        tmdb_id: TMDB identifier if found
        title: Consensus title from parsers (based on weighted voting)
        year: Consensus year from parsers
        media_type: Granular media type (movie, tv_episode, tv_season, tv_multi_season, tv_show)
        season: Season number(s) if TV content
        episode: Episode number(s) if TV content
        confidence: Title confidence level (based on parser agreement ONLY)
        parser_used: Name(s) of parser(s) used
        tmdb_match: Whether TMDB validation succeeded
        metadata: Additional metadata including 'title_confidence' with voting details

    Properties:
        medium: Broad media category ('TV' or 'MOVIE') derived from media_type.
                This is simpler than media_type and required for TMDB lookups.
        confidence_value: Numeric confidence value (0.0-1.0)

    Output Modes:
        to_dict(detail=False): Returns only core detection properties (default)
            - imdb_id, tmdb_id, title, year
            - media_type (granular: "movie", "tv_episode", "tv_season", "tv_multi_season", "tv_show")
            - medium (simplified: "TV" or "MOVIE")
            - confidence (numeric value)
            - tmdb_match
            - season, episode (for TV content only)

        to_dict(detail=True): Returns core properties plus detailed metadata in 'detail' key
            - All core properties
            - detail.parser_used: Which parser(s) were used
            - detail.confidence_level: Confidence level name (HIGH, MEDIUM, LOW)
            - detail.overview, poster_path, genres, etc.: Rich TMDB metadata
            - detail.consensus: Parser agreement statistics
            - detail.title_confidence: Weighted voting details
            - detail.episodes, episode_summary: Episode extraction details (for TV)
    """
    imdb_id: Optional[str]
    tmdb_id: Optional[int]
    title: str
    year: Optional[int]
    media_type: MediaType
    season: Optional[int]
    episode: Optional[int]
    confidence: ConfidenceLevel
    parser_used: str
    tmdb_match: bool
    metadata: Dict[str, Any]

    def __post_init__(self):
        """Ensure proper data types"""
        # Convert string media_type to MediaType enum (for cached data)
        if isinstance(self.media_type, str):
            try:
                self.media_type = MediaType(self.media_type)
            except ValueError:
                # If invalid string, default to UNKNOWN
                self.media_type = MediaType.UNKNOWN

        # Convert numeric confidence to ConfidenceLevel enum
        if isinstance(self.confidence, (int, float)):
            if self.confidence >= 0.9:
                self.confidence = ConfidenceLevel.HIGH
            elif self.confidence >= 0.7:
                self.confidence = ConfidenceLevel.MEDIUM
            elif self.confidence >= 0.5:
                self.confidence = ConfidenceLevel.LOW
            else:
                self.confidence = ConfidenceLevel.VERY_LOW

    @property
    def confidence_value(self) -> float:
        """Get confidence as numeric value"""
        return self.confidence.value

    @property
    def medium(self) -> str:
        """
        Get the broad media category (TV or MOVIE).

        This is simpler than media_type and is required for TMDB lookups.
        Returns 'TV' for all TV-related types, 'MOVIE' for movies, 'UNKNOWN' otherwise.
        """
        if self.media_type == MediaType.MOVIE:
            return 'MOVIE'
        elif self.media_type in [MediaType.TV_SHOW, MediaType.TV_EPISODE, MediaType.TV_SEASON, MediaType.TV_MULTI_SEASON]:
            return 'TV'
        else:
            return 'UNKNOWN'

    def to_dict(self, detail: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Args:
            detail: If True, include detailed metadata. If False (default),
                   return only core detection properties.

        Returns:
            Dictionary with core properties and optionally detailed metadata
        """
        # Core properties always included
        result = {
            'imdb_id': self.imdb_id,
            'tmdb_id': self.tmdb_id,
            'title': self.title,
            'year': self.year,
            'media_type': self.media_type.value,
            'medium': self.medium,
            'confidence': self.confidence_value,
            'tmdb_match': self.tmdb_match,
        }

        # Add season/episode for TV content
        if self.medium == "TV":
            result['season'] = self.season
            result['episode'] = self.episode

        # Add detailed information if requested
        if detail:
            result['detail'] = {
                'parser_used': self.parser_used,
                'confidence_level': self.confidence.name,
                **self.metadata
            }

        return result


@dataclass
class DatasetSample:
    """Represents a sample from the torrent dataset"""
    name: str
    size: int
    imdb_id: Optional[str]
    type: str
    files: List[Dict[str, Any]]
    sample_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatasetSample':
        """Create DatasetSample from dictionary"""
        return cls(
            name=data['name'],
            size=data['size'],
            imdb_id=data.get('imdb_id'),
            type=data['type'],
            files=data['files'],
            sample_id=data['sample_id']
        )

    def get_file_paths(self) -> List[str]:
        """Extract just the file paths"""
        return [file_info['path'] for file_info in self.files]

    def has_imdb_id(self) -> bool:
        """Check if sample has an IMDB ID"""
        return self.imdb_id is not None and self.imdb_id != ''

    def is_tv_show(self) -> bool:
        """Check if sample is classified as TV show"""
        return self.type == 'tv'

    def is_movie(self) -> bool:
        """Check if sample is classified as movie"""
        return self.type == 'movie'