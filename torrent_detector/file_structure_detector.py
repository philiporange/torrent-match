"""
File structure-based torrent content detection.

This module analyzes the file structure and file sizes within torrents to determine
content type. Different media types have distinct file organization patterns:

- Movies: Single large video file dominating (>50%) of total torrent size
- Episodes: Similar to movies, typically one dominant video file
- Seasons: Folder containing multiple similarly-sized video files
- Multi-season torrents: Multiple folders, each containing similarly-sized video files

This provides complementary detection alongside name-based parsing.
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
import statistics

from .models import MediaType


class FileStructureDetector:
    """Analyzes torrent file structure to determine content type"""

    def __init__(self):
        self.video_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv',
            '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
            '.m2ts', '.ts', '.vob', '.3gp', '.ogm', '.mk3d'
        }

        # Patterns for detecting season folders
        self.season_patterns = [
            r'Season\s*(\d+)',
            r'S(\d+)',
            r'Series\s*(\d+)',
            r'Temporada\s*(\d+)',
            r'Saison\s*(\d+)',
            r'Staffel\s*(\d+)',
        ]

    def detect_media_type(
        self,
        files: List[Dict[str, any]],
        torrent_name: str = ""
    ) -> MediaType:
        """
        Detect media type based on file structure and sizes.

        Args:
            files: List of file dictionaries with 'path' and 'length' keys
            torrent_name: Optional torrent name for additional context

        Returns:
            MediaType classification based on file structure analysis
        """
        media_type, _ = self.detect_media_type_with_confidence(files, torrent_name)
        return media_type

    def detect_media_type_with_confidence(
        self,
        files: List[Dict[str, any]],
        torrent_name: str = ""
    ) -> Tuple[MediaType, float]:
        """
        Detect media type based on file structure with confidence level.

        Confidence levels:
        - 0.9-1.0: Very confident (multiple season folders, clear patterns)
        - 0.7-0.9: Confident (single season folder, similarly-sized files)
        - 0.5-0.7: Moderate (dominant file with episode indicators)
        - 0.3-0.5: Low (weak patterns, ambiguous structure)
        - 0.0-0.3: Very low (no clear patterns)

        Args:
            files: List of file dictionaries with 'path' and 'length' keys
            torrent_name: Optional torrent name for additional context

        Returns:
            Tuple of (MediaType, confidence) where confidence is 0.0-1.0
        """
        if not files:
            return MediaType.UNKNOWN, 0.0

        # Extract video files and their information
        video_files = self._extract_video_files(files)

        if not video_files:
            return MediaType.UNKNOWN, 0.0

        # Calculate total torrent size
        total_size = sum(f['length'] for f in files)

        # Analyze folder structure
        folder_analysis = self._analyze_folder_structure(video_files)

        # Check for season folders
        season_folders = self._detect_season_folders(video_files)

        # Determine media type based on structure with confidence
        if len(season_folders) > 1:
            # Multiple season folders = multi-season torrent (very confident)
            return MediaType.TV_MULTI_SEASON, 0.95
        elif len(season_folders) == 1:
            # Single season folder = season pack (very confident)
            return MediaType.TV_SEASON, 0.9

        # Check if we have multiple videos in the same directory
        if folder_analysis['max_videos_in_folder'] >= 4:
            # Multiple videos in same folder - likely a season
            if self._are_files_similarly_sized(
                [f for f in video_files if Path(f['path']).parent == folder_analysis['folder_with_most_videos']]
            ):
                # Multiple similarly-sized videos = confident it's a season
                return MediaType.TV_SEASON, 0.8
            else:
                # Multiple videos but not similarly sized = less confident
                return MediaType.TV_SEASON, 0.6

        # Analyze individual large video files
        if len(video_files) == 1:
            # Single video file
            video_size = video_files[0]['length']
            if video_size / total_size > 0.5:
                # Single dominant file = movie or single episode
                # Differentiate based on torrent name if possible
                if self._has_episode_indicators(torrent_name) or self._has_episode_indicators(video_files[0]['path']):
                    return MediaType.TV_EPISODE, 0.7
                else:
                    return MediaType.MOVIE, 0.7
            else:
                # Not dominant - unclear
                return MediaType.UNKNOWN, 0.2
        elif len(video_files) <= 3:
            # Small number of videos - check if one dominates
            largest_video = max(video_files, key=lambda f: f['length'])
            if largest_video['length'] / total_size > 0.5:
                # One file dominates - likely movie or episode
                if self._has_episode_indicators(torrent_name) or self._has_episode_indicators(largest_video['path']):
                    return MediaType.TV_EPISODE, 0.6
                else:
                    return MediaType.MOVIE, 0.6
            else:
                # Multiple similarly-sized videos - could be a mini-season or movie collection
                if self._are_files_similarly_sized(video_files):
                    return MediaType.TV_SEASON, 0.7
                else:
                    return MediaType.UNKNOWN, 0.3
        else:
            # Many video files - likely TV season
            if self._are_files_similarly_sized(video_files):
                return MediaType.TV_SEASON, 0.75
            else:
                # Many videos but not similarly sized
                return MediaType.TV_SEASON, 0.5

    def _extract_video_files(self, files: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """
        Extract only video files from the file list.

        Args:
            files: List of all files with path and length

        Returns:
            List of video files only
        """
        video_files = []
        for file_info in files:
            path = file_info.get('path', '')
            length = file_info.get('length', 0)

            if Path(path).suffix.lower() in self.video_extensions:
                video_files.append({
                    'path': path,
                    'length': length,
                    'name': Path(path).name
                })

        return video_files

    def _analyze_folder_structure(self, video_files: List[Dict[str, any]]) -> Dict[str, any]:
        """
        Analyze the folder organization of video files.

        Args:
            video_files: List of video file dictionaries

        Returns:
            Dictionary with folder structure analysis
        """
        folder_counts = defaultdict(int)

        for video in video_files:
            parent = Path(video['path']).parent
            folder_counts[parent] += 1

        if folder_counts:
            folder_with_most_videos = max(folder_counts, key=folder_counts.get)
            max_videos = folder_counts[folder_with_most_videos]
        else:
            folder_with_most_videos = None
            max_videos = 0

        return {
            'total_folders': len(folder_counts),
            'folder_with_most_videos': folder_with_most_videos,
            'max_videos_in_folder': max_videos,
            'folder_counts': dict(folder_counts)
        }

    def _detect_season_folders(self, video_files: List[Dict[str, any]]) -> Set[str]:
        """
        Detect folders that match season naming patterns.

        Args:
            video_files: List of video file dictionaries

        Returns:
            Set of folder paths that appear to be season folders
        """
        season_folders = set()

        for video in video_files:
            path_parts = Path(video['path']).parts

            # Check each part of the path for season patterns
            for part in path_parts[:-1]:  # Exclude filename itself
                for pattern in self.season_patterns:
                    if re.search(pattern, part, re.IGNORECASE):
                        # Found a season folder
                        season_folders.add(part)
                        break

        return season_folders

    def _are_files_similarly_sized(
        self,
        files: List[Dict[str, any]],
        threshold: float = 0.3
    ) -> bool:
        """
        Check if files are similarly sized (coefficient of variation < threshold).

        Args:
            files: List of file dictionaries with 'length' key
            threshold: Maximum coefficient of variation to consider files similar

        Returns:
            True if files are similarly sized, False otherwise
        """
        if len(files) < 2:
            return False

        sizes = [f['length'] for f in files]

        # Calculate coefficient of variation (std dev / mean)
        mean_size = statistics.mean(sizes)
        if mean_size == 0:
            return False

        std_dev = statistics.stdev(sizes)
        coeff_variation = std_dev / mean_size

        return coeff_variation < threshold

    def _has_episode_indicators(self, text: str) -> bool:
        """
        Check if text contains episode indicators.

        Args:
            text: Text to check (torrent name or file path)

        Returns:
            True if episode indicators found
        """
        episode_patterns = [
            r'S\d+E\d+',  # S01E01
            r'\d+x\d+',  # 1x01
            r'Episode\s*\d+',  # Episode 01
            r'E\d+(?![\dx])',  # E01
            r'Part\s*\d+',  # Part 1
            r'Ep\.?\s*\d+',  # Ep. 01
            r'\d{4}\.\d{1,2}\.\d{1,2}',  # Date-based episodes (2023.10.15)
        ]

        for pattern in episode_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def get_dominant_video_info(
        self,
        files: List[Dict[str, any]]
    ) -> Optional[Dict[str, any]]:
        """
        Get information about the dominant video file (if one exists).

        Args:
            files: List of file dictionaries

        Returns:
            Dictionary with dominant video info or None if no dominant file
        """
        video_files = self._extract_video_files(files)

        if not video_files:
            return None

        total_size = sum(f['length'] for f in files)
        largest_video = max(video_files, key=lambda f: f['length'])

        dominance_ratio = largest_video['length'] / total_size

        if dominance_ratio > 0.5:
            return {
                'path': largest_video['path'],
                'size': largest_video['length'],
                'dominance_ratio': dominance_ratio,
                'is_dominant': True
            }

        return {
            'path': largest_video['path'],
            'size': largest_video['length'],
            'dominance_ratio': dominance_ratio,
            'is_dominant': False
        }

    def get_video_file_summary(
        self,
        files: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """
        Get comprehensive summary of video files in the torrent.

        Args:
            files: List of file dictionaries

        Returns:
            Dictionary with video file statistics and analysis
        """
        video_files = self._extract_video_files(files)

        if not video_files:
            return {
                'count': 0,
                'total_size': 0,
                'has_dominant_file': False,
                'season_folders': 0,
                'suggested_type': MediaType.UNKNOWN
            }

        total_size = sum(f['length'] for f in files)
        video_total_size = sum(f['length'] for f in video_files)

        folder_analysis = self._analyze_folder_structure(video_files)
        season_folders = self._detect_season_folders(video_files)
        dominant_info = self.get_dominant_video_info(files)

        return {
            'count': len(video_files),
            'total_size': video_total_size,
            'percentage_of_torrent': video_total_size / total_size if total_size > 0 else 0,
            'has_dominant_file': dominant_info['is_dominant'] if dominant_info else False,
            'dominant_ratio': dominant_info['dominance_ratio'] if dominant_info else 0,
            'season_folders': len(season_folders),
            'folders_with_videos': folder_analysis['total_folders'],
            'max_videos_in_folder': folder_analysis['max_videos_in_folder'],
            'suggested_type': self.detect_media_type(files)
        }
