"""
ReBulk parser implementation.

Custom parser using the ReBulk library for pattern matching.
This parser extracts title, year, season, episode, and metadata
"""

import re
from typing import Optional

from rebulk import Rebulk

from ..models import ParseResult, MediaType, TorrentContent
from ..verbose import vprint
from .base import Parser


class ReBulkParser(Parser):
    """Custom parser using ReBulk for specific patterns"""

    def is_available(self) -> bool:
        return True

    def __init__(self):
        self.rebulk = self._build_rebulk()

    def _build_rebulk(self) -> "Rebulk":
        """Build custom ReBulk rules"""
        rebulk = Rebulk()

        # Custom title pattern - title followed by year
        rebulk.regex(
            r"^(.+?)[\.\s]+(19\d{2}|20\d{2})", name="title_year", children=True
        )

        # TV show patterns - season and episode
        rebulk.regex(r"S(\d+)E(\d+)", name="season_episode")
        rebulk.regex(r"(\d+)x(\d+)", name="season_episode_alt")

        # TV show patterns - season only (without episode)
        rebulk.regex(r"\bS(\d+)(?!E\d+)\b", name="season_only")

        # Year pattern
        rebulk.regex(r"\b(19\d{2}|20\d{2})\b", name="year")

        # Quality patterns
        rebulk.regex(r"\b(2160p|1080p|720p|480p|4K)\b", name="quality")

        # Codec patterns
        rebulk.regex(r"\b(x264|x265|h264|h265|HEVC|XViD)\b", name="codec")

        return rebulk

    def parse(self, name: str, content: TorrentContent) -> Optional[ParseResult]:
        try:
            matches = self.rebulk.matches(name)

            # Extract data from matches
            result_data = {}
            has_season_only = False

            for match in matches:
                if match.name == "title_year" and match.children:
                    result_data["title"] = match.children[0].value
                    result_data["year"] = int(match.children[1].value)
                elif match.name == "year" and "year" not in result_data:
                    result_data["year"] = int(match.value)
                elif match.name in ["season_episode", "season_episode_alt"]:
                    if match.children:
                        result_data["season"] = int(match.children[0].value)
                        result_data["episode"] = int(match.children[1].value)
                elif match.name == "season_only":
                    # S01 without E01 - indicates season pack
                    if match.children:
                        result_data["season"] = int(match.children[0].value)
                    else:
                        # Extract season number from the match
                        season_match = re.search(r"S(\d+)", match.value, re.IGNORECASE)
                        if season_match:
                            result_data["season"] = int(season_match.group(1))
                    has_season_only = True
                elif match.name == "quality":
                    result_data["quality"] = match.value.upper()
                elif match.name == "codec":
                    result_data["codec"] = match.value.upper()

            if not result_data.get("title"):
                # Fallback title extraction - extract everything before season/episode patterns
                clean_name = (
                    content.normalized_name if content.normalized_name else name
                )

                # Try to extract title before season/episode markers
                title_match = re.match(
                    r"^(.+?)(?:\s+S\d+|\s+\d{4}|\s+Season|\s+Complete)",
                    clean_name,
                    re.IGNORECASE,
                )
                if title_match:
                    result_data["title"] = title_match.group(1).strip()
                else:
                    # Final fallback - everything before year or first number pattern
                    title_match = re.match(r"^(.+?)(?:\s+\d{4}|$)", clean_name)
                    if title_match:
                        result_data["title"] = title_match.group(1).strip()

            # Use preprocessor's media type if it's more specific than our mapping
            mapped_type = self._determine_type(result_data, content, has_season_only)
            final_type = (
                content.media_type
                if content.media_type != MediaType.UNKNOWN
                else mapped_type
            )

            # If preprocessor detected TV content and ReBulk says episode,
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
                codec=result_data.get("codec"),
                group=None,
                parser_name="ReBulk",
                raw_data=result_data,
            )
        except Exception as e:
            vprint(f"ReBulk parsing failed for '{name}': {e}")
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
