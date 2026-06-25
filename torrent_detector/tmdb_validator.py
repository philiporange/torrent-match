"""
TMDB integration for validating and enriching parsed results.

This module handles TMDB API lookups to validate parsed media information
and retrieve IMDB IDs and additional metadata using the local tmdb library.
"""

import json
import os
from typing import Optional, Tuple, Dict, Any

from tmdb.api import TMDbAPI, Media
from tmdb.cache import TMDbCache
from tmdb.index import TMDbIndex
from tmdb.db import initialize_db, kv

import redislite
from .verbose import vprint
from .models import ParseResult, MediaIdentification, MediaType, ConfidenceLevel


class TMDBValidator:
    """Validate and enrich results using TMDB API via local tmdb library"""

    def __init__(self, api_key: str, cache_db_path: str = "/tmp/torrent_interpret.db"):
        """
        Initialize TMDB validator.

        Args:
            api_key: TMDB API key
            cache_db_path: Path to redislite database file for result caching
        """
        # Set API key in environment for tmdb library
        os.environ['TMDB_API_KEY'] = api_key

        # Initialize tmdb API
        self.api = TMDbAPI()

        # Initialize redislite for caching validation results
        self.cache = redislite.Redis(cache_db_path) if cache_db_path else None
        if self.cache:
            vprint(f"Using redislite cache at: {cache_db_path}")

    def validate_and_enrich(self, parse_result: ParseResult) -> Tuple[bool, Optional[MediaIdentification]]:
        """
        Validate parse result against TMDB and get IMDB ID.

        When media type is certain (MOVIE or TV), validates against that type only.
        When uncertain (UNKNOWN), checks both movie and TV types and returns the best match
        based on title similarity and match quality.

        Args:
            parse_result: Result from parser to validate

        Returns:
            Tuple of (success, MediaIdentification) or (False, None)
        """
        if not parse_result.title:
            return False, None

        # Try to validate based on detected media type
        if parse_result.media_type == MediaType.MOVIE:
            return self._validate_movie(parse_result)
        elif parse_result.media_type in [MediaType.TV_EPISODE, MediaType.TV_SEASON, MediaType.TV_MULTI_SEASON, MediaType.TV_SHOW]:
            return self._validate_tv_show(parse_result)

        # If unknown or uncertain, check BOTH types and pick the best match
        vprint(f"TMDB: Media type uncertain for '{parse_result.title}', checking both movie and TV")

        movie_result = self._validate_movie(parse_result)
        tv_result = self._validate_tv_show(parse_result)

        # If both failed, return failure
        if not movie_result[0] and not tv_result[0]:
            return False, None

        # If only one succeeded, return that one
        if movie_result[0] and not tv_result[0]:
            vprint(f"TMDB: Only movie match found for '{parse_result.title}'")
            return movie_result
        if tv_result[0] and not movie_result[0]:
            vprint(f"TMDB: Only TV match found for '{parse_result.title}'")
            return tv_result

        # Both succeeded - pick the better match based on title similarity
        movie_ident = movie_result[1]
        tv_ident = tv_result[1]

        movie_score = self._calculate_match_score(parse_result.title, movie_ident.title)
        tv_score = self._calculate_match_score(parse_result.title, tv_ident.title)

        vprint(f"TMDB: Both movie and TV matches found - Movie score: {movie_score:.3f}, TV score: {tv_score:.3f}")

        if movie_score >= tv_score:
            vprint(f"TMDB: Selecting movie match '{movie_ident.title}'")
            return movie_result
        else:
            vprint(f"TMDB: Selecting TV match '{tv_ident.title}'")
            return tv_result

    def _validate_movie(self, parse_result: ParseResult) -> Tuple[bool, Optional[MediaIdentification]]:
        """Validate movie against TMDB"""
        try:
            # Check cache first
            cache_key = self._get_cache_key('movie', parse_result.title, parse_result.year)
            if self.cache:
                cached_result = self.cache.get(cache_key)
                if cached_result:
                    data = json.loads(cached_result)
                    # Remove computed properties that aren't constructor arguments
                    data.pop('medium', None)
                    data.pop('confidence_value', None)
                    vprint(f"TMDB: Cache hit for movie: {parse_result.title}")
                    return True, MediaIdentification(**data)

            vprint(f"TMDB: Searching for movie: {parse_result.title} ({parse_result.year})")

            # Use tmdb API to find best match
            match = self.api.match(
                title=parse_result.title,
                year=parse_result.year,
                media=Media.MOVIE
            )

            if not match:
                vprint(f"TMDB: No match found for movie: {parse_result.title}")
                return False, None

            # Get full details including IMDB ID
            tmdb_id = match.get('id')
            unified_id = f"movie:{tmdb_id}"

            vprint(f"TMDB: Getting details for {unified_id}")
            details = self.api.get_details(unified_id=unified_id)

            if not details:
                return False, None

            # Extract IMDB ID
            imdb_id = details.get('imdb_id')

            # Calculate match score for title similarity
            match_score = self._calculate_match_score(
                parse_result.title,
                match.get('title', '')
            )

            # Calculate confidence based on match score
            # Parser confidence is no longer used - final confidence is determined
            # by consensus in the detector, but we use match score for TMDB match quality
            confidence = self._calculate_final_confidence(
                match_score,  # Use match score as base confidence
                match_score
            )

            identification = MediaIdentification(
                imdb_id=imdb_id,
                tmdb_id=tmdb_id,
                title=match['title'],
                year=int(str(match.get('release_date', ''))[:4]) if match.get('release_date') else None,
                media_type=MediaType.MOVIE,
                season=None,
                episode=None,
                confidence=confidence,
                parser_used=parse_result.parser_name,
                tmdb_match=True,
                metadata={
                    'overview': details.get('overview'),
                    'poster_path': details.get('poster_path'),
                    'vote_average': details.get('vote_average'),
                    'vote_count': details.get('vote_count'),
                    'original_language': details.get('original_language'),
                    'popularity': details.get('popularity'),
                    'genres': [g['name'] for g in details.get('genres', [])],
                    'runtime': details.get('runtime'),
                }
            )

            # Cache successful result
            if self.cache and identification.imdb_id:
                self.cache.setex(
                    cache_key,
                    86400,  # 24 hours
                    json.dumps(identification.to_dict())
                )
                vprint(f"TMDB: Cached movie result for: {parse_result.title}")

            return True, identification

        except Exception as e:
            vprint(f"TMDB movie validation failed for {parse_result.title}: {e}")
            import traceback
            vprint(traceback.format_exc())
            return False, None

    def _validate_tv_show(self, parse_result: ParseResult) -> Tuple[bool, Optional[MediaIdentification]]:
        """Validate TV show against TMDB"""
        try:
            # Check cache first
            cache_key = self._get_cache_key('tv', parse_result.title, parse_result.year)
            if self.cache:
                cached_result = self.cache.get(cache_key)
                if cached_result:
                    data = json.loads(cached_result)
                    # Remove computed properties that aren't constructor arguments
                    data.pop('medium', None)
                    data.pop('confidence_value', None)
                    vprint(f"TMDB: Cache hit for TV show: {parse_result.title}")
                    return True, MediaIdentification(**data)

            vprint(f"TMDB: Searching for TV show: {parse_result.title} ({parse_result.year})")

            # Use tmdb API to find best match
            match = self.api.match(
                title=parse_result.title,
                year=parse_result.year,
                media=Media.TV
            )

            if not match:
                vprint(f"TMDB: No match found for TV show: {parse_result.title}")
                return False, None

            # Get full details including external IDs
            tmdb_id = match.get('id')
            unified_id = f"tv:{tmdb_id}"

            vprint(f"TMDB: Getting details for {unified_id}")
            details = self.api.get_details(unified_id=unified_id)

            if not details:
                return False, None

            # Extract IMDB ID from external_ids
            imdb_id = None
            if 'external_ids' in details:
                imdb_id = details['external_ids'].get('imdb_id')

            # Calculate match score for confidence adjustment
            match_score = self._calculate_match_score(
                parse_result.title,
                match.get('name', '')
            )

            # Calculate confidence based on match score
            # Parser confidence is no longer used - final confidence is determined
            # by consensus in the detector, but we use match score for TMDB match quality
            confidence = self._calculate_final_confidence(
                match_score,  # Use match score as base confidence
                match_score
            )

            # Preserve specific TV media type from parser (TV_EPISODE, TV_SEASON, TV_MULTI_SEASON)
            # Only use generic TV_SHOW if parser didn't provide a specific type
            tv_media_type = parse_result.media_type
            if tv_media_type not in [MediaType.TV_EPISODE, MediaType.TV_SEASON, MediaType.TV_MULTI_SEASON]:
                tv_media_type = MediaType.TV_SHOW

            identification = MediaIdentification(
                imdb_id=imdb_id,
                tmdb_id=tmdb_id,
                title=match['name'],
                year=int(str(match.get('first_air_date', ''))[:4]) if match.get('first_air_date') else None,
                media_type=tv_media_type,
                season=parse_result.season,
                episode=parse_result.episode,
                confidence=confidence,
                parser_used=parse_result.parser_name,
                tmdb_match=True,
                metadata={
                    'overview': details.get('overview'),
                    'poster_path': details.get('poster_path'),
                    'vote_average': details.get('vote_average'),
                    'vote_count': details.get('vote_count'),
                    'original_language': details.get('original_language'),
                    'popularity': details.get('popularity'),
                    'number_of_seasons': details.get('number_of_seasons'),
                    'number_of_episodes': details.get('number_of_episodes'),
                    'status': details.get('status'),
                    'genres': [g['name'] for g in details.get('genres', [])],
                }
            )

            # Cache successful result
            if self.cache and identification.imdb_id:
                self.cache.setex(
                    cache_key,
                    86400,  # 24 hours
                    json.dumps(identification.to_dict())
                )
                vprint(f"TMDB: Cached TV result for: {parse_result.title}")

            return True, identification

        except Exception as e:
            vprint(f"TMDB TV validation failed for {parse_result.title}: {e}")
            import traceback
            vprint(traceback.format_exc())
            return False, None

    def _calculate_match_score(self, query: str, title: str) -> float:
        """
        Calculate similarity score between query and title.

        Args:
            query: Original search query
            title: TMDB title to compare against

        Returns:
            Similarity score between 0.0 and 1.0
        """
        import difflib

        # Normalize both strings
        query_normalized = query.lower().strip()
        title_normalized = title.lower().strip()

        # Use difflib for fuzzy matching
        base_score = difflib.SequenceMatcher(None, query_normalized, title_normalized).ratio()

        # Bonus for exact word matches
        query_words = set(query_normalized.split())
        title_words = set(title_normalized.split())

        if query_words and title_words:
            word_overlap = len(query_words.intersection(title_words))
            word_bonus = word_overlap / max(len(query_words), len(title_words))
            base_score = min(base_score + (word_bonus * 0.2), 1.0)

        return base_score

    def _calculate_final_confidence(self, parser_confidence: float, match_score: float) -> ConfidenceLevel:
        """
        Calculate final confidence level.

        Args:
            parser_confidence: Confidence from the parser
            match_score: TMDB title match score

        Returns:
            Final ConfidenceLevel
        """
        combined_score = (parser_confidence + match_score) / 2

        if combined_score >= 0.85:
            return ConfidenceLevel.HIGH
        elif combined_score >= 0.7:
            return ConfidenceLevel.MEDIUM
        elif combined_score >= 0.5:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def _get_cache_key(self, media_type: str, title: str, year: Optional[int]) -> str:
        """Generate cache key for query"""
        import hashlib

        key_parts = [media_type, title.lower()]
        if year:
            key_parts.append(str(year))

        key_string = ":".join(key_parts)
        return f"tmdb:{hashlib.md5(key_string.encode()).hexdigest()}"

    def search_by_imdb_id(self, imdb_id: str) -> Optional[MediaIdentification]:
        """
        Search TMDB by IMDB ID (useful for validation).

        Args:
            imdb_id: IMDB ID to search for

        Returns:
            MediaIdentification if found, None otherwise
        """
        try:
            # Check cache first
            cache_key = f"imdb:{imdb_id}"
            if self.cache:
                cached_result = self.cache.get(cache_key)
                if cached_result:
                    data = json.loads(cached_result)
                    # Remove computed properties that aren't constructor arguments
                    data.pop('medium', None)
                    data.pop('confidence_value', None)
                    vprint(f"TMDB: Cache hit for IMDB ID: {imdb_id}")
                    return MediaIdentification(**data)

            vprint(f"TMDB: Looking up IMDB ID: {imdb_id}")

            # Get details using IMDB ID
            details = self.api.get_details(imdb_id=imdb_id)

            if not details:
                vprint(f"TMDB: No result for IMDB ID: {imdb_id}")
                return None

            # Determine if it's a movie or TV show based on response
            is_movie = 'title' in details
            tmdb_id = details.get('id')

            if is_movie:
                identification = MediaIdentification(
                    imdb_id=imdb_id,
                    tmdb_id=tmdb_id,
                    title=details['title'],
                    year=int(str(details.get('release_date', ''))[:4]) if details.get('release_date') else None,
                    media_type=MediaType.MOVIE,
                    season=None,
                    episode=None,
                    confidence=ConfidenceLevel.HIGH,
                    parser_used='IMDB_Lookup',
                    tmdb_match=True,
                    metadata={
                        'overview': details.get('overview'),
                        'poster_path': details.get('poster_path'),
                        'vote_average': details.get('vote_average'),
                        'original_language': details.get('original_language')
                    }
                )
            else:
                identification = MediaIdentification(
                    imdb_id=imdb_id,
                    tmdb_id=tmdb_id,
                    title=details.get('name', details.get('original_name')),
                    year=int(str(details.get('first_air_date', ''))[:4]) if details.get('first_air_date') else None,
                    media_type=MediaType.TV_SHOW,
                    season=None,
                    episode=None,
                    confidence=ConfidenceLevel.HIGH,
                    parser_used='IMDB_Lookup',
                    tmdb_match=True,
                    metadata={
                        'overview': details.get('overview'),
                        'poster_path': details.get('poster_path'),
                        'vote_average': details.get('vote_average'),
                        'number_of_seasons': details.get('number_of_seasons')
                    }
                )

            # Cache result
            if self.cache:
                self.cache.setex(cache_key, 86400, json.dumps(identification.to_dict()))
                vprint(f"TMDB: Cached IMDB lookup result for: {imdb_id}")

            return identification

        except Exception as e:
            vprint(f"TMDB IMDB lookup failed for {imdb_id}: {e}")
            import traceback
            vprint(traceback.format_exc())
            return None


def create_tmdb_validator(api_key: str, cache_db_path: str = "/tmp/torrent_interpret.db") -> TMDBValidator:
    """
    Create TMDB validator with redislite caching.

    Args:
        api_key: TMDB API key
        cache_db_path: Path to redislite database file

    Returns:
        TMDBValidator instance
    """
    return TMDBValidator(api_key, cache_db_path)
