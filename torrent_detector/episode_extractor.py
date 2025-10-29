"""
Episode extraction from torrent file structures.

This module extracts specific episode information (season and episode numbers) from
torrent file lists by analyzing both folder names and filenames. It handles various
naming conventions including:

- Standard formats: S01E01, S01E02-E03 (multi-episode)
- Alternative formats: 1x01, 101 (shorthand)
- Specials: S00E01 (Season 0 episodes)
- Combined episodes: S01E01-E02, S01E01E02

The extractor parses folder structures to determine season context and extracts
episode numbers from video filenames.
"""

import re
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict


class EpisodeExtractor:
    """Extracts episode information from torrent file structures"""

    def __init__(self):
        self.video_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv',
            '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
            '.m2ts', '.ts', '.vob', '.3gp', '.ogm', '.mk3d'
        }

        # Episode patterns in order of specificity
        # Group 1: Season, Group 2: Episode start, Group 3: Optional episode end
        self.episode_patterns = [
            # S01E01-E02, S01E01-02 (range with dash)
            (r'\b[Ss](\d{1,2})[Ee](\d{1,3})(?:-[Ee]?(\d{1,3}))\b', 'standard_range'),
            # S01E01E02 (no separator)
            (r'\b[Ss](\d{1,2})[Ee](\d{1,3})[Ee](\d{1,3})\b', 'standard_multi'),
            # S01E01 (standard)
            (r'\b[Ss](\d{1,2})[Ee](\d{1,3})\b', 'standard'),
            # 1x01-1x02 (with dash and repeat)
            (r'\b(\d{1,2})[xX](\d{1,3})-\d{1,2}[xX](\d{1,3})\b', 'x_format_range'),
            # 1x01-02 (simplified range)
            (r'\b(\d{1,2})[xX](\d{1,3})-(\d{1,3})\b', 'x_format_range_simple'),
            # 1x01 (alternative format)
            (r'\b(\d{1,2})[xX](\d{1,3})\b', 'x_format'),
            # Episode 01, Ep 01, E 01 (explicit episode marker)
            (r'\b(?:Episode|Ep\.?|E)\s*(\d{1,3})\b', 'explicit_episode'),
            # Part 01 (for multi-part episodes)
            (r'\bPart\s*(\d{1,3})\b', 'part'),
        ]

        # Season folder patterns
        self.season_folder_patterns = [
            (r'\bSeason\s*(\d{1,2})\b', 'season'),
            (r'\bS(\d{1,2})\b', 's_format'),
            (r'\bSeries\s*(\d{1,2})\b', 'series'),
            (r'\bTemporada\s*(\d{1,2})\b', 'temporada'),
            (r'\bSaison\s*(\d{1,2})\b', 'saison'),
            (r'\bStaffel\s*(\d{1,2})\b', 'staffel'),
        ]

    def extract_episodes(
        self,
        files: List[Dict[str, any]],
        include_specials: bool = True
    ) -> List[Dict[str, int]]:
        """
        Extract list of episodes from file structure.

        Args:
            files: List of file dictionaries with 'path' key (and optionally 'size')
            include_specials: Whether to include Season 0 (specials)

        Returns:
            List of episode dictionaries with 'season' and 'episode' keys,
            sorted by season and episode number
        """
        episodes_set = set()  # Use set to avoid duplicates

        for file_info in files:
            path = file_info.get('path', file_info.get('name', ''))

            # Only process video files
            if not self._is_video_file(path):
                continue

            # Extract season and episode information
            extracted = self._extract_from_path(path)

            if extracted:
                for season, episode in extracted:
                    # Filter specials if needed
                    if not include_specials and season == 0:
                        continue
                    episodes_set.add((season, episode))

        # Convert to list of dicts and sort
        episodes = [{'season': s, 'episode': e} for s, e in episodes_set]
        episodes.sort(key=lambda x: (x['season'], x['episode']))

        return episodes

    def extract_episodes_by_season(
        self,
        files: List[Dict[str, any]],
        include_specials: bool = True
    ) -> Dict[int, List[int]]:
        """
        Extract episodes grouped by season.

        Args:
            files: List of file dictionaries with 'path' key
            include_specials: Whether to include Season 0 (specials)

        Returns:
            Dictionary mapping season numbers to sorted lists of episode numbers
        """
        episodes = self.extract_episodes(files, include_specials)

        # Group by season
        by_season = defaultdict(list)
        for ep in episodes:
            by_season[ep['season']].append(ep['episode'])

        # Sort episode lists
        for season in by_season:
            by_season[season].sort()

        return dict(by_season)

    def get_episode_count_summary(
        self,
        files: List[Dict[str, any]],
        include_specials: bool = True
    ) -> Dict[str, any]:
        """
        Get summary statistics about episodes in the torrent.

        Args:
            files: List of file dictionaries with 'path' key
            include_specials: Whether to include Season 0 (specials)

        Returns:
            Dictionary with episode statistics
        """
        episodes_by_season = self.extract_episodes_by_season(files, include_specials)

        total_episodes = sum(len(eps) for eps in episodes_by_season.values())
        season_count = len(episodes_by_season)

        # Get episode ranges per season
        season_ranges = {}
        for season, episodes in episodes_by_season.items():
            if episodes:
                season_ranges[season] = {
                    'min': min(episodes),
                    'max': max(episodes),
                    'count': len(episodes),
                    'episodes': episodes
                }

        return {
            'total_episodes': total_episodes,
            'season_count': season_count,
            'seasons': list(episodes_by_season.keys()),
            'season_ranges': season_ranges,
            'has_specials': 0 in episodes_by_season,
        }

    def _is_video_file(self, path: str) -> bool:
        """Check if file is a video file based on extension"""
        return Path(path).suffix.lower() in self.video_extensions

    def _extract_from_path(self, path: str) -> List[Tuple[int, int]]:
        """
        Extract season and episode numbers from a file path.

        Args:
            path: File path to analyze

        Returns:
            List of (season, episode) tuples (may contain multiple for multi-episode files)
        """
        # Get path components
        path_obj = Path(path)
        filename = path_obj.stem  # Filename without extension
        parent_folders = path_obj.parts[:-1]  # All folder names

        # First, try to extract season from folder structure
        season_from_folder = self._extract_season_from_folders(parent_folders)

        # Extract episodes from filename
        episodes_info = self._extract_episodes_from_filename(filename)

        results = []

        for episode_data in episodes_info:
            # Determine final season number
            if episode_data['season'] is not None:
                # Filename has explicit season
                season = episode_data['season']
            elif season_from_folder is not None:
                # Use season from folder
                season = season_from_folder
            else:
                # No season information - skip this file
                continue

            # Add all episodes (may be multiple for multi-episode files)
            for episode_num in episode_data['episodes']:
                results.append((season, episode_num))

        return results

    def _extract_season_from_folders(self, folders: Tuple[str, ...]) -> Optional[int]:
        """
        Extract season number from folder names.

        Args:
            folders: Tuple of folder names in the path

        Returns:
            Season number if found, None otherwise
        """
        # Check folders from most specific (closest to file) to least specific
        for folder in reversed(folders):
            for pattern, pattern_type in self.season_folder_patterns:
                match = re.search(pattern, folder, re.IGNORECASE)
                if match:
                    return int(match.group(1))

        return None

    def _extract_episodes_from_filename(self, filename: str) -> List[Dict[str, any]]:
        """
        Extract episode information from filename.

        Args:
            filename: Filename (without extension) to analyze

        Returns:
            List of episode info dicts with 'season' and 'episodes' keys
        """
        results = []

        for pattern, pattern_type in self.episode_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)

            if match:
                if pattern_type == 'standard_range':
                    # S01E01-E02 or S01E01-02
                    season = int(match.group(1))
                    ep_start = int(match.group(2))
                    ep_end = int(match.group(3))
                    episodes = list(range(ep_start, ep_end + 1))
                    results.append({'season': season, 'episodes': episodes})
                    break

                elif pattern_type == 'standard_multi':
                    # S01E01E02
                    season = int(match.group(1))
                    ep1 = int(match.group(2))
                    ep2 = int(match.group(3))
                    results.append({'season': season, 'episodes': [ep1, ep2]})
                    break

                elif pattern_type == 'standard':
                    # S01E01
                    season = int(match.group(1))
                    episode = int(match.group(2))
                    results.append({'season': season, 'episodes': [episode]})
                    break

                elif pattern_type in ['x_format_range', 'x_format_range_simple']:
                    # 1x01-02 or 1x01-1x02
                    season = int(match.group(1))
                    ep_start = int(match.group(2))
                    ep_end = int(match.group(3))
                    episodes = list(range(ep_start, ep_end + 1))
                    results.append({'season': season, 'episodes': episodes})
                    break

                elif pattern_type == 'x_format':
                    # 1x01
                    season = int(match.group(1))
                    episode = int(match.group(2))
                    results.append({'season': season, 'episodes': [episode]})
                    break

                elif pattern_type in ['explicit_episode', 'part']:
                    # Episode 01, Part 01 - no season in pattern, use folder season
                    episode = int(match.group(1))
                    results.append({'season': None, 'episodes': [episode]})
                    break

        return results

    def format_episode_list(
        self,
        episodes: List[Dict[str, int]],
        format_style: str = 'standard'
    ) -> List[str]:
        """
        Format episode list as strings.

        Args:
            episodes: List of episode dicts with 'season' and 'episode' keys
            format_style: Format style ('standard' for S01E01, 'x' for 1x01)

        Returns:
            List of formatted episode strings
        """
        formatted = []

        for ep in episodes:
            if format_style == 'x':
                formatted.append(f"{ep['season']}x{ep['episode']:02d}")
            else:  # standard
                formatted.append(f"S{ep['season']:02d}E{ep['episode']:02d}")

        return formatted

    def detect_missing_episodes(
        self,
        files: List[Dict[str, any]],
        season: Optional[int] = None
    ) -> Dict[int, List[int]]:
        """
        Detect potentially missing episodes based on gaps in episode numbers.

        Args:
            files: List of file dictionaries with 'path' key
            season: Optional specific season to check (None = check all seasons)

        Returns:
            Dictionary mapping season numbers to lists of potentially missing episode numbers
        """
        episodes_by_season = self.extract_episodes_by_season(files, include_specials=False)

        missing = {}

        # Filter to specific season if requested
        seasons_to_check = [season] if season is not None else episodes_by_season.keys()

        for s in seasons_to_check:
            if s not in episodes_by_season or s == 0:  # Skip specials
                continue

            episodes = episodes_by_season[s]

            if len(episodes) < 2:
                continue  # Need at least 2 episodes to detect gaps

            # Find gaps
            min_ep = min(episodes)
            max_ep = max(episodes)
            expected = set(range(min_ep, max_ep + 1))
            actual = set(episodes)
            gaps = sorted(expected - actual)

            if gaps:
                missing[s] = gaps

        return missing
