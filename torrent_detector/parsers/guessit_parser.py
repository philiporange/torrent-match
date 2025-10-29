"""
GuessIt parser implementation.

Primary parser using the GuessIt library for torrent name parsing.
This parser extracts title, year, season, episode, and metadata
"""

from typing import Optional

import guessit

from ..models import ParseResult, MediaType, TorrentContent
from ..verbose import vprint
from .base import Parser


class GuessItParser(Parser):
    """Primary parser using GuessIt library"""

    def is_available(self) -> bool:
        return True

    def parse(self, name: str, content: TorrentContent) -> Optional[ParseResult]:
        if not self.is_available():
            return None

        try:
            # Use media type hint if available
            options = {}
            if content.media_type == MediaType.MOVIE:
                options["type"] = "movie"
            elif content.media_type in [
                MediaType.TV_EPISODE,
                MediaType.TV_SEASON,
                MediaType.TV_MULTI_SEASON,
            ]:
                options["type"] = "episode"

            result = guessit.guessit(name, options)

            # Use preprocessor's media type if it's more specific than our mapping
            mapped_type = self._map_media_type(result.get("type"))
            final_type = (
                content.media_type
                if content.media_type != MediaType.UNKNOWN
                else mapped_type
            )

            # If preprocessor detected TV content and GuessIt says episode,
            # prefer the preprocessor's more specific classification
            if mapped_type == MediaType.TV_EPISODE and content.media_type in [
                MediaType.TV_SEASON,
                MediaType.TV_MULTI_SEASON,
            ]:
                final_type = content.media_type

            # If GuessIt detected a season but no episode, classify as season pack
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
                quality=result.get("screen_size"),
                source=result.get("source"),
                codec=result.get("video_codec"),
                group=result.get("release_group"),
                parser_name="GuessIt",
                raw_data=dict(result),
            )
        except Exception as e:
            vprint(f"GuessIt parsing failed for '{name}': {e}")
            return None

    def _map_media_type(self, type_str: Optional[str]) -> MediaType:
        if type_str == "movie":
            return MediaType.MOVIE
        elif type_str in ["episode", "series"]:
            return MediaType.TV_EPISODE  # Default to episode for GuessIt
        return MediaType.UNKNOWN
