"""
TMDB enricher for adding comprehensive media information using the local tmdb library.

This module uses the local tmdb cache and API for richer media metadata including
posters, cast, crew, genres, ratings, and more. It provides an offline-capable
enhancement to the standard TMDB validation.
"""

from typing import Optional, Dict, Any, Tuple
import os

try:
    from tmdb.api import TMDbAPI, Media
    from tmdb.cache import TMDbCache
    from tmdb.index import TMDbIndex
    from tmdb.db import initialize_db, kv
    TMDB_LOCAL_AVAILABLE = True
except ImportError:
    TMDB_LOCAL_AVAILABLE = False
    TMDbAPI = None
    TMDbCache = None
    TMDbIndex = None
    Media = None

from .verbose import vprint
from .models import ParseResult, MediaIdentification, MediaType, ConfidenceLevel


class TMDBEnricher:
    """
    Enrich media identifications with comprehensive TMDB data using the local cache.

    This enricher uses the local tmdb library which provides:
    - Offline-capable local cache of popular media
    - Fuzzy search capabilities
    - Rich metadata including posters, cast, crew, genres, etc.
    - Efficient batch processing
    """

    def __init__(self,
                 api_key: Optional[str] = None,
                 cache_db_path: str = "/tmp/torrent_match/tmdb.sqlite",
                 use_local_cache: bool = True,
                 min_popularity: float = 10.0):
        """
        Initialize TMDB enricher with local cache.

        Args:
            api_key: TMDB API key (uses TMDB_API_KEY env var if not provided)
            cache_db_path: Path to SQLite cache database
            use_local_cache: Whether to use local cache for offline lookups
            min_popularity: Minimum popularity threshold for cached items
        """
        if not TMDB_LOCAL_AVAILABLE:
            raise ImportError(
                "Local tmdb library not available. Install it from ~/Code/tmdb or "
                "use the standard TMDBValidator instead."
            )

        # Get API key from env if not provided
        self.api_key = api_key or os.environ.get('TMDB_API_KEY')
        if not self.api_key:
            raise ValueError("TMDB_API_KEY environment variable or api_key parameter required")

        self.use_local_cache = use_local_cache
        self.min_popularity = min_popularity

        # Initialize local tmdb components
        vprint(f"Initializing TMDB enricher with local cache at: {cache_db_path}")

        # Set environment variable for tmdb library
        os.environ['TMDB_API_KEY'] = self.api_key

        # Initialize database if using local cache
        if use_local_cache:
            os.environ['TMDB_DB_PATH'] = cache_db_path
            initialize_db()
            vprint("TMDB local database initialized")

        # Initialize API client
        self.api = TMDbAPI()

        # Initialize cache and index if using local cache
        if use_local_cache:
            self.index = TMDbIndex(api=self.api, kv=kv)
            self.cache = TMDbCache(api=self.api, index=self.index)
            vprint("TMDB local cache and index initialized")
        else:
            self.index = None
            self.cache = None

    def enrich(self, identification: MediaIdentification) -> MediaIdentification:
        """
        Enrich an existing MediaIdentification with additional TMDB data.

        Args:
            identification: MediaIdentification to enrich

        Returns:
            Enriched MediaIdentification with additional metadata
        """
        if not identification.title:
            return identification

        vprint(f"Enriching: {identification.title} ({identification.year})")

        try:
            # Determine media type
            if identification.media_type == MediaType.MOVIE:
                media = Media.MOVIE
            else:
                media = Media.TV

            # Try to find best match using local cache first
            if self.use_local_cache and self.index:
                match_result = self._search_local_cache(
                    title=identification.title,
                    year=identification.year,
                    media=media
                )
            else:
                match_result = None

            # Fall back to API search if not in cache
            if not match_result:
                match_result = self._search_via_api(
                    title=identification.title,
                    year=identification.year,
                    media=media
                )

            if not match_result:
                vprint(f"No enrichment data found for: {identification.title}")
                return identification

            # Get detailed information
            details = self._get_details(match_result, media)

            if not details:
                return identification

            # Enrich the identification with additional metadata
            enriched_metadata = {
                **(identification.metadata or {}),
                'tmdb_id': match_result.get('id'),
                'overview': details.get('overview'),
                'poster_path': details.get('poster_path'),
                'backdrop_path': details.get('backdrop_path'),
                'vote_average': details.get('vote_average'),
                'vote_count': details.get('vote_count'),
                'popularity': details.get('popularity'),
                'original_language': details.get('original_language'),
                'original_title': details.get('original_title' if media == Media.MOVIE else 'original_name'),
                'genres': [g['name'] for g in details.get('genres', [])],
                'production_companies': [c['name'] for c in details.get('production_companies', [])],
                'production_countries': [c['name'] for c in details.get('production_countries', [])],
                'spoken_languages': [l['english_name'] for l in details.get('spoken_languages', [])],
            }

            # Add media-specific fields
            if media == Media.MOVIE:
                enriched_metadata.update({
                    'runtime': details.get('runtime'),
                    'budget': details.get('budget'),
                    'revenue': details.get('revenue'),
                    'tagline': details.get('tagline'),
                })
            else:
                enriched_metadata.update({
                    'number_of_seasons': details.get('number_of_seasons'),
                    'number_of_episodes': details.get('number_of_episodes'),
                    'episode_run_time': details.get('episode_run_time'),
                    'status': details.get('status'),
                    'type': details.get('type'),
                    'first_air_date': details.get('first_air_date'),
                    'last_air_date': details.get('last_air_date'),
                })

            # Add cast and crew if available
            if 'credits' in details:
                enriched_metadata['cast'] = [
                    {
                        'name': actor['name'],
                        'character': actor.get('character'),
                        'order': actor.get('order'),
                    }
                    for actor in details['credits'].get('cast', [])[:10]  # Top 10 actors
                ]

                enriched_metadata['crew'] = [
                    {
                        'name': crew['name'],
                        'job': crew.get('job'),
                        'department': crew.get('department'),
                    }
                    for crew in details['credits'].get('crew', [])
                    if crew.get('job') in ['Director', 'Writer', 'Producer', 'Executive Producer']
                ][:10]

            # Update IMDB ID if not present but available in details
            imdb_id = identification.imdb_id
            if not imdb_id:
                if media == Media.MOVIE:
                    imdb_id = details.get('imdb_id')
                elif 'external_ids' in details:
                    imdb_id = details['external_ids'].get('imdb_id')

            # Create enriched identification
            enriched = MediaIdentification(
                imdb_id=imdb_id or identification.imdb_id,
                tmdb_id=match_result.get('id'),
                title=identification.title,
                year=identification.year,
                media_type=identification.media_type,
                season=identification.season,
                episode=identification.episode,
                confidence=identification.confidence,
                parser_used=identification.parser_used,
                tmdb_match=True,
                metadata=enriched_metadata
            )

            vprint(f"Successfully enriched: {identification.title}")
            return enriched

        except Exception as e:
            vprint(f"Error enriching {identification.title}: {e}")
            return identification

    def _search_local_cache(self, title: str, year: Optional[int], media: Media) -> Optional[Dict[str, Any]]:
        """
        Search for media in local cache using fuzzy matching.

        Args:
            title: Media title
            year: Release year
            media: Media type (Movie or TV)

        Returns:
            Best match result or None
        """
        try:
            if not self.index:
                return None

            vprint(f"Searching local cache for: {title} ({year}) - {media}")

            # Use fuzzy search from index
            results = self.index.search(
                query=title,
                media=media,
                limit=5
            )

            if not results:
                vprint("No results in local cache")
                return None

            # Find best match considering year
            best_match = self._find_best_match(title, year, results, media)

            if best_match:
                vprint(f"Found in local cache: {best_match.get('title' if media == Media.MOVIE else 'name')}")

            return best_match

        except Exception as e:
            vprint(f"Error searching local cache: {e}")
            return None

    def _search_via_api(self, title: str, year: Optional[int], media: Media) -> Optional[Dict[str, Any]]:
        """
        Search for media via TMDB API.

        Args:
            title: Media title
            year: Release year
            media: Media type (Movie or TV)

        Returns:
            Best match result or None
        """
        try:
            vprint(f"Searching via API for: {title} ({year}) - {media}")

            # Use API match method for best result
            result = self.api.match(
                title=title,
                year=year,
                media=media
            )

            if result:
                vprint(f"Found via API: {result.get('title' if media == Media.MOVIE else 'name')}")

            return result

        except Exception as e:
            vprint(f"Error searching via API: {e}")
            return None

    def _find_best_match(self,
                        title: str,
                        year: Optional[int],
                        results: list,
                        media: Media) -> Optional[Dict[str, Any]]:
        """
        Find best matching result from search results.

        Args:
            title: Original search title
            year: Expected release year
            results: List of search results
            media: Media type

        Returns:
            Best matching result or None
        """
        if not results:
            return None

        title_key = 'title' if media == Media.MOVIE else 'name'
        date_key = 'release_date' if media == Media.MOVIE else 'first_air_date'

        # Calculate match scores
        scored_results = []
        for result in results:
            result_title = result.get(title_key, '')
            result_date = result.get(date_key, '')
            result_year = int(result_date[:4]) if result_date and len(result_date) >= 4 else None

            # Title similarity score
            title_score = self._calculate_title_similarity(title, result_title)

            # Year match score
            year_score = 1.0
            if year and result_year:
                year_diff = abs(year - result_year)
                if year_diff == 0:
                    year_score = 1.0
                elif year_diff <= 1:
                    year_score = 0.8
                elif year_diff <= 2:
                    year_score = 0.5
                else:
                    year_score = 0.2

            # Combined score
            combined_score = (title_score * 0.7) + (year_score * 0.3)

            scored_results.append((combined_score, result))

        # Sort by score
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # Return best match if score is high enough
        if scored_results[0][0] >= 0.6:
            return scored_results[0][1]

        return None

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate similarity between two titles.

        Args:
            title1: First title
            title2: Second title

        Returns:
            Similarity score between 0.0 and 1.0
        """
        import difflib

        # Normalize
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()

        # Use difflib for fuzzy matching
        return difflib.SequenceMatcher(None, t1, t2).ratio()

    def _get_details(self, result: Dict[str, Any], media: Media) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a media item.

        Args:
            result: Search result with media ID
            media: Media type

        Returns:
            Detailed media information or None
        """
        try:
            media_id = result.get('id')
            if not media_id:
                return None

            # Use unified ID format
            unified_id = f"{'movie' if media == Media.MOVIE else 'tv'}:{media_id}"

            vprint(f"Fetching details for: {unified_id}")

            # Get details via API
            details = self.api.get_details(unified_id=unified_id)

            return details

        except Exception as e:
            vprint(f"Error getting details: {e}")
            return None

    def ensure_cache(self, media: Media = Media.MOVIE, min_popularity: Optional[float] = None):
        """
        Ensure local cache is populated and fresh.

        Args:
            media: Media type to cache (Movie or TV)
            min_popularity: Minimum popularity threshold (uses instance default if not provided)
        """
        if not self.use_local_cache or not self.cache:
            vprint("Local cache not enabled")
            return

        min_pop = min_popularity or self.min_popularity

        vprint(f"Ensuring cache for {media} (min_popularity={min_pop})")
        self.cache.ensure_cache(media=media, min_popularity=min_pop)
        vprint(f"Cache ready for {media}")

    def download_poster(self, identification: MediaIdentification) -> Optional[str]:
        """
        Download poster for a media identification.

        Args:
            identification: MediaIdentification with TMDB ID

        Returns:
            Path to downloaded poster file or None
        """
        try:
            tmdb_id = identification.tmdb_id or identification.metadata.get('tmdb_id')
            if not tmdb_id:
                vprint("No TMDB ID available for poster download")
                return None

            media_type = 'movie' if identification.media_type == MediaType.MOVIE else 'tv'
            unified_id = f"{media_type}:{tmdb_id}"

            vprint(f"Downloading poster for: {unified_id}")
            poster_path = self.api.poster(unified_id=unified_id)

            vprint(f"Poster downloaded to: {poster_path}")
            return poster_path

        except Exception as e:
            vprint(f"Error downloading poster: {e}")
            return None


def create_tmdb_enricher(
    api_key: Optional[str] = None,
    cache_db_path: str = "/tmp/torrent_match/tmdb.sqlite",
    use_local_cache: bool = True,
    min_popularity: float = 10.0
) -> TMDBEnricher:
    """
    Create TMDB enricher with local cache.

    Args:
        api_key: TMDB API key (uses TMDB_API_KEY env var if not provided)
        cache_db_path: Path to SQLite cache database
        use_local_cache: Whether to use local cache for offline lookups
        min_popularity: Minimum popularity threshold for cached items

    Returns:
        TMDBEnricher instance
    """
    return TMDBEnricher(
        api_key=api_key,
        cache_db_path=cache_db_path,
        use_local_cache=use_local_cache,
        min_popularity=min_popularity
    )
