"""
PTN parser implementation.

Secondary parser using the parse-torrent-title (PTN) library.
This parser extracts title, year, season, episode, and metadata
"""

from typing import Optional

import PTN

from ..models import ParseResult, MediaType, TorrentContent
from ..verbose import vprint
from .base import Parser


class PTNParser(Parser):
    """Secondary parser using parse-torrent-title"""

    def is_available(self) -> bool:
        return True

    def parse(self, name: str, content: TorrentContent) -> Optional[ParseResult]:
        if not self.is_available():
            return None

        try:
            result = PTN.parse(name)

            # Use preprocessor's media type if it's more specific than our mapping
            mapped_type = self._determine_type(result, content)
            final_type = (
                content.media_type
                if content.media_type != MediaType.UNKNOWN
                else mapped_type
            )

            # If preprocessor detected TV content and PTN says episode,
            # prefer the preprocessor's more specific classification
            if mapped_type == MediaType.TV_EPISODE and content.media_type in [
                MediaType.TV_SEASON,
                MediaType.TV_MULTI_SEASON,
            ]:
                final_type = content.media_type

            # If PTN detected a season but no episode, classify as season pack
            if (
                result.get("season")
                and not result.get("episode")
                and mapped_type == MediaType.TV_EPISODE
            ):
                final_type = MediaType.TV_SEASON

            return ParseResult(
                title=result.get("title"),
                year=result.get("year"),
                season=result.get("season"),
                episode=result.get("episode"),
                media_type=final_type,
                quality=result.get("quality"),
                source=None,  # PTN doesn't extract source
                codec=result.get("codec"),
                group=result.get("group"),
                parser_name="PTN",
                raw_data=result,
            )
        except Exception as e:
            vprint(f"PTN parsing failed for '{name}': {e}")
            return None

    def _determine_type(self, result: dict, content: TorrentContent) -> MediaType:
        if result.get("season") or result.get("episode"):
            return MediaType.TV_EPISODE  # Default to episode for PTN
        if content.media_type != MediaType.UNKNOWN:
            return content.media_type
        return MediaType.MOVIE
