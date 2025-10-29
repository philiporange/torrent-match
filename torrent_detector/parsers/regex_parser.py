"""
Regex parser implementation.

Basic regex-based parser as a fallback option.
This parser extracts title, year, season, episode, and metadata
"""

import re
from typing import Optional

from ..models import ParseResult, MediaType, TorrentContent
from ..verbose import vprint
from .base import Parser


class RegexParser(Parser):
    """Basic regex-based parser as fallback"""

    def is_available(self) -> bool:
        return True  # Always available as it uses built-in regex

    def parse(self, name: str, content: TorrentContent) -> Optional[ParseResult]:
        try:
            result_data = {}
            has_season_only = False

            # Extract year first (from any pattern) to know if we should truncate at it
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", name)
            year = int(year_match.group(1)) if year_match else None

            # Extract title by truncating at various patterns in priority order
            title = name

            # 1. Truncate at bracketed year: (YYYY) or [YYYY]
            if year:
                title = re.sub(r"\s*[\(\[]" + str(year) + r"[\)\]].*$", "", title)
                # Also truncate at any bracketed content after the year
                title = re.sub(r"\s*[\(\[].*$", "", title)

            # 2. Truncate at year followed by dots/spaces (for cases like 1977.1080p)
            if year:
                title = re.sub(r"\s*[\.\s]+" + str(year) + r"[\.\s].*$", "", title)

            # 3. Truncate at season/episode patterns
            title = re.split(
                r"[\.\s]+(?:S\d+(?:E\d+)?|\d+x\d+)", title, flags=re.IGNORECASE
            )[0]

            # 4. Truncate at any remaining bracketed content
            title = re.sub(r"\s*[\(\[].*$", "", title)

            # 5. Truncate at quality patterns (common torrent indicators)
            title = re.sub(
                r"[\.\s]+(?:1080p|720p|480p|2160p|4K|HDTV|BluRay|WEBRip|WEB-DL).*$",
                "",
                title,
                flags=re.IGNORECASE,
            )

            # 4. Clean up the title
            title = title.replace(".", " ").replace("_", " ")
            title = re.sub(r"\s+", " ", title).strip()

            result_data["title"] = title
            result_data["year"] = year

            # Extract episode info - first check for full season+episode
            episode_match = re.search(r"S(\d+)E(\d+)", name, re.IGNORECASE)
            if episode_match:
                result_data["season"] = int(episode_match.group(1))
                result_data["episode"] = int(episode_match.group(2))
            else:
                # Check for season-only pattern (S01 without E01)
                season_only_match = re.search(
                    r"\bS(\d+)(?!E\d+)\b", name, re.IGNORECASE
                )
                if season_only_match:
                    result_data["season"] = int(season_only_match.group(1))
                    has_season_only = True
                else:
                    # Check for alternative format (1x02)
                    alt_episode_match = re.search(r"(\d+)x(\d+)", name)
                    if alt_episode_match:
                        result_data["season"] = int(alt_episode_match.group(1))
                        result_data["episode"] = int(alt_episode_match.group(2))

            # Extract quality
            quality_match = re.search(
                r"\b(2160p|1080p|720p|480p|4K)\b", name, re.IGNORECASE
            )
            if quality_match:
                result_data["quality"] = quality_match.group(1).upper()

            # Extract year if not already found
            if "year" not in result_data:
                year_match = re.search(r"\b(19\d{2}|20\d{2})\b", name)
                if year_match:
                    result_data["year"] = int(year_match.group(1))

            # Clean title
            if result_data.get("title"):
                result_data["title"] = re.sub(r"[._-]", " ", result_data["title"])
                result_data["title"] = re.sub(r"\s+", " ", result_data["title"]).strip()

            # Use preprocessor's media type if it's more specific than our mapping
            mapped_type = self._determine_type(result_data, content, has_season_only)
            final_type = (
                content.media_type
                if content.media_type != MediaType.UNKNOWN
                else mapped_type
            )

            # If preprocessor detected TV content and Regex says episode,
            # prefer the preprocessor's more specific classification
            if mapped_type == MediaType.TV_EPISODE and content.media_type in [
                MediaType.TV_SEASON,
                MediaType.TV_MULTI_SEASON,
            ]:
                final_type = content.media_type

            # If we detected season-only pattern, prefer TV_SEASON over TV_EPISODE
            if (
                has_season_only
                and result_data.get("season")
                and not result_data.get("episode")
            ):
                final_type = MediaType.TV_SEASON

            return ParseResult(
                title=result_data.get("title"),
                year=result_data.get("year"),
                season=result_data.get("season"),
                episode=result_data.get("episode"),
                media_type=final_type,
                quality=result_data.get("quality"),
                source=None,
                codec=None,
                group=None,
                parser_name="Regex",
                raw_data=result_data,
            )
        except Exception as e:
            vprint(f"Regex parsing failed for '{name}': {e}")
            return None

    def _determine_type(
        self, result: dict, content: TorrentContent, has_season_only: bool = False
    ) -> MediaType:
        # If we have season but no episode, it's likely a season pack
        if result.get("season") and not result.get("episode"):
            return MediaType.TV_SEASON
        # If we have both season and episode, it's an episode
        if result.get("season") or result.get("episode"):
            return MediaType.TV_EPISODE
        return (
            content.media_type
            if content.media_type != MediaType.UNKNOWN
            else MediaType.MOVIE
        )
