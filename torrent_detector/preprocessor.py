"""
Pre-processing module for torrent content detection.

This module handles name normalization and basic file enumeration to prepare
torrent data for parsing by the detection pipeline. File structure-based detection
is handled by the file_structure_detector module.
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import unicodedata

from .models import MediaType, TorrentContent


class PreProcessor:
    """Pre-process torrent names and file structures"""

    # Common release patterns to remove for title extraction
    RELEASE_PATTERNS = [
        r'\[.*?\]',  # Remove brackets content
        r'\b(1080p|720p|480p|2160p|4K|8K)\b',
        r'\b(BluRay|BRRip|WEB-DL|WEBRip|HDTV|DVDRip|DVDSCR|CAM|TS|TC)\b',
        r'\b(x264|x265|h264|h265|HEVC|AVC|XViD)\b',
        r'\b(AAC|AC3|DTS|TrueHD|Atmos|FLAC|MP3)\b',
        r'\b(REPACK|PROPER|EXTENDED|UNRATED|DIRECTORS\.CUT|THEATRICAL\.CUT)\b',
        r'\b(HDCAM|HDTS|TS|CAM|DVDRIP|DVDSCR)\b',
    ]

    # TV show folder patterns
    SEASON_PATTERNS = [
        r'Season\s*(\d+)',
        r'S(\d+)',
        r'Series\s*(\d+)',
        r'Temporada\s*(\d+)',
        r'Saison\s*(\d+)',
        r'Staffel\s*(\d+)',
    ]

    # Episode patterns in filenames
    EPISODE_PATTERNS = [
        r'S(\d+)E(\d+)',  # S01E01
        r'(\d+)x(\d+)',  # 1x01
        r'Episode\s*(\d+)',  # Episode 01
        r'E(\d+)(?![\dx])',  # E01 (but not E01x02)
        r'Part\s*(\d+)',  # Part 1
        r'Ep\.?\s*(\d+)',  # Ep. 01
    ]

    # TV show date patterns (daily shows with air dates)
    TV_DATE_PATTERNS = [
        r'\d{4}[.\-]\d{1,2}[.\-]\d{1,2}',  # YYYY.MM.DD or YYYY-MM-DD
        r'\d{4}\s\d{1,2}\s\d{1,2}',  # YYYY MM DD
    ]

    def __init__(self):
        self.video_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv',
            '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
            '.m2ts', '.ts', '.vob', '.3gp', '.ogm', '.mk3d'
        }

    def normalize_name(self, name: str) -> str:
        """
        Normalize torrent/file name for better matching.

        Args:
            name: Original torrent or file name

        Returns:
            Normalized name with release info removed
        """
        # Remove unicode characters and normalize
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')

        # Replace common separators with spaces
        name = re.sub(r'[._\-\[\]()]', ' ', name)

        # Remove multiple spaces
        name = re.sub(r'\s+', ' ', name)

        # Remove release info for title extraction
        clean_name = name
        for pattern in self.RELEASE_PATTERNS:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)

        # Remove trailing release group names
        clean_name = re.sub(r'\s+[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?\s*$', '', clean_name)

        return clean_name.strip()

    def analyze_file_structure(self, files: List[str], torrent_name: str = None) -> TorrentContent:
        """
        Build basic file structure representation.

        Note: This method only builds the folder structure and counts video files.
        Media type detection based on file structure is handled by FileStructureDetector.

        Args:
            files: List of file paths in the torrent
            torrent_name: Original torrent name for pattern analysis

        Returns:
            TorrentContent object with basic file information
        """
        video_files = []
        folder_structure = {}
        has_season_folders = False

        for file_path in files:
            path = Path(file_path)

            # Check if it's a video file
            if path.suffix.lower() in self.video_extensions:
                video_files.append(file_path)

            # Build folder structure
            parts = path.parts
            current = folder_structure
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

                # Check for season folders
                for pattern in self.SEASON_PATTERNS:
                    if re.search(pattern, part, re.IGNORECASE):
                        has_season_folders = True

        # Media type is set to UNKNOWN - will be determined by parsers and FileStructureDetector
        return TorrentContent(
            torrent_name=torrent_name or "",
            files=files,
            folder_structure=folder_structure,
            media_type=MediaType.UNKNOWN,
            movie_file_count=len(video_files),
            has_season_folders=has_season_folders,
            normalized_name=""
        )



    def _detect_season_patterns_in_name(self, torrent_name: str) -> Optional[Dict[str, str]]:
        """
        Detect season patterns in torrent name.

        Args:
            torrent_name: The torrent name to analyze

        Returns:
            Dictionary with season type info or None if no patterns found
        """
        if not torrent_name:
            return None

        # Pattern for single season: S01, Season 1, etc.
        single_season_patterns = [
            r'\bS(\d{1,2})\b(?![\s]*E\d+)',  # S01 (but not S01E01)
            r'\bSeason\s*(\d{1,2})\b',
            r'\bSeries\s*(\d{1,2})\b',
        ]

        # Pattern for multiple seasons: S01-S05, Seasons 1-5, etc.
        multi_season_patterns = [
            r'\bS(\d{1,2})[-~]S?(\d{1,2})\b',  # S01-S05 or S01-S5
            r'\bSeasons\s*(\d{1,2})[-~]\s*(\d{1,2})\b',
            r'\bComplete\s+Series\b',
            r'\bAll\s+Seasons\b',
            r'\bFull\s+Series\b',
        ]

        # Check for multi-season patterns first (more specific)
        for pattern in multi_season_patterns:
            match = re.search(pattern, torrent_name, re.IGNORECASE)
            if match:
                return {'type': 'multi', 'pattern': pattern, 'match': match.group()}

        # Check for single season patterns
        for pattern in single_season_patterns:
            match = re.search(pattern, torrent_name, re.IGNORECASE)
            if match:
                return {'type': 'single', 'pattern': pattern, 'match': match.group()}

        return None


    def extract_year_from_name(self, name: str) -> Optional[int]:
        """
        Extract year from torrent or file name.

        Args:
            name: Name to search for year in

        Returns:
            Year if found, None otherwise
        """
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
        if year_match:
            return int(year_match.group(1))
        return None

    def extract_quality_from_name(self, name: str) -> Optional[str]:
        """
        Extract video quality from name.

        Args:
            name: Name to search for quality in

        Returns:
            Quality string if found, None otherwise
        """
        quality_patterns = [
            r'\b(2160p|4K)\b',
            r'\b(1080p)\b',
            r'\b(720p)\b',
            r'\b(480p)\b',
            r'\b(360p)\b',
        ]

        for pattern in quality_patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        return None

    def extract_codec_from_name(self, name: str) -> Optional[str]:
        """
        Extract video codec from name.

        Args:
            name: Name to search for codec in

        Returns:
            Codec string if found, None otherwise
        """
        codec_patterns = [
            r'\b(x265|HEVC)\b',
            r'\b(x264|h264)\b',
            r'\b(XViD)\b',
            r'\b(AVC)\b',
        ]

        for pattern in codec_patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        return None

    def extract_release_group(self, name: str) -> Optional[str]:
        """
        Extract release group from name.

        Args:
            name: Name to search for release group in

        Returns:
            Release group name if found, None otherwise
        """
        # Look for patterns like -GROUPNAME at the end
        group_match = re.search(r'-([A-Za-z0-9]+)$', name)
        if group_match:
            return group_match.group(1)

        # Look for patterns like [GROUPNAME]
        bracket_match = re.search(r'\[([A-Za-z0-9]+)\]', name)
        if bracket_match:
            return bracket_match.group(1)

        return None

    def clean_title(self, title: str) -> str:
        """
        Clean and normalize a title.

        Args:
            title: Raw title string

        Returns:
            Cleaned title
        """
        if not title:
            return ""

        # Remove extra whitespace
        title = re.sub(r'\s+', ' ', title).strip()

        # Remove leading/trailing special characters
        title = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', title)

        # Capitalize words properly
        title = ' '.join(word.capitalize() for word in title.split())

        return title

    def detect_media_type_from_name(self, torrent_name: str) -> Tuple[Optional[MediaType], float]:
        """
        Detect media type from torrent name with confidence level.

        Uses hierarchical pattern matching with definitive rules:
        - S01E01 format = definitive TV episode (confidence: 1.0)
        - Full dates (2020.11.12) = almost always TV episode (confidence: 0.95)
        - S01, Season 1, S4 Complete = strong hints for TV series (confidence: 0.8-0.9)
        - Title (year) without above = hint for movie (confidence: 0.6)

        Args:
            torrent_name: The torrent name to analyze

        Returns:
            Tuple of (MediaType, confidence) where confidence is 0.0-1.0,
            or (None, 0.0) if no strong indicators found
        """
        if not torrent_name:
            return None, 0.0

        # DEFINITIVE TV EPISODE: S01E01, 1x01 format
        for pattern in [r'S\d+E\d+', r'\d+x\d+']:
            if re.search(pattern, torrent_name, re.IGNORECASE):
                return MediaType.TV_EPISODE, 1.0

        # ALMOST DEFINITIVE TV EPISODE: Full date format (YYYY.MM.DD)
        if re.search(r'\d{4}[.\-]\d{1,2}[.\-]\d{1,2}', torrent_name):
            return MediaType.TV_EPISODE, 0.95

        # STRONG TV HINTS: Season indicators
        # Multi-season patterns
        multi_season_patterns = [
            r'\bS\d{1,2}[-~]S?\d{1,2}\b',  # S01-S05
            r'\bSeasons?\s*\d{1,2}[-~]\s*\d{1,2}\b',  # Seasons 1-5
            r'\bComplete[\s.]+Series\b',  # Complete Series
            r'\bAll\s+Seasons?\b',  # All Seasons
            r'\bFull[\s.]+(?:Series|Season)\b',  # Full Series
        ]
        for pattern in multi_season_patterns:
            if re.search(pattern, torrent_name, re.IGNORECASE):
                return MediaType.TV_MULTI_SEASON, 0.9

        # Single season patterns (but NOT episode)
        single_season_patterns = [
            r'\bS\d{1,2}[\s.]+Complete\b',  # S01 Complete
            r'\bSeason[\s.]*\d{1,2}[\s.]+Complete\b',  # Season 1 Complete, Season.1.Complete
            r'\bSeason[\s.]*\d{1,2}\b',  # Season 1, Season.1
            r'\bS\d{1,2}\b(?!E\d+)',  # S01 (but not S01E01)
        ]
        for pattern in single_season_patterns:
            if re.search(pattern, torrent_name, re.IGNORECASE):
                return MediaType.TV_SEASON, 0.85

        # MEDIUM TV HINTS: Other episode indicators
        other_tv_patterns = [
            r'\bEpisode\s*\d+\b',  # Episode 01
            r'\bE\d+\b',  # E01
            r'\bEp\.?\s*\d+\b',  # Ep. 01
            r'\bPart\s*\d+\b',  # Part 1
        ]
        for pattern in other_tv_patterns:
            if re.search(pattern, torrent_name, re.IGNORECASE):
                return MediaType.TV_EPISODE, 0.8

        # MOVIE HINT: Title (Year) format without TV indicators
        # Look for year in parentheses or after title
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        if re.search(year_pattern, torrent_name):
            # Check if it looks like a standard movie format
            # Title Year Quality Source (no TV indicators)
            if not any(re.search(p, torrent_name, re.IGNORECASE) for p in [
                r'\bSeason\b', r'\bS\d+\b', r'\bEpisode\b', r'\bE\d+\b',
                r'\bSeries\b', r'\bComplete\b'
            ]):
                return MediaType.MOVIE, 0.6

        # No strong indicators found
        return None, 0.0