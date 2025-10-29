#!/usr/bin/env python3
"""
Simple example showing how to use torrent_match library.
"""

from torrent_match import match, match_batch, TorrentMatcher

# Example 1: Simple matching with the convenience function
print("=" * 60)
print("Example 1: Simple match")
print("=" * 60)

result = match("The.Matrix.1999.1080p.BluRay.x264-SPARKS")
print(f"Title: {result.title}")
print(f"Year: {result.year}")
print(f"IMDB ID: {result.imdb_id}")
print(f"Confidence: {result.confidence.name}")
print()

# Example 2: Match with files
print("=" * 60)
print("Example 2: Match with file information")
print("=" * 60)

result = match(
    "Breaking.Bad.S05E14.720p.HDTV.x264-KILLERS",
    files=["Breaking.Bad.S05E14.720p.HDTV.x264-KILLERS.mkv"]
)
print(f"Title: {result.title}")
print(f"Season: {result.season}")
print(f"Episode: {result.episode}")
print(f"Media Type: {result.media_type.value}")
print()

# Example 3: Batch matching
print("=" * 60)
print("Example 3: Batch matching")
print("=" * 60)

torrents = [
    "Inception.2010.1080p.BluRay.x264",
    "Game.of.Thrones.S08E06.1080p.WEB-DL",
    "The.Dark.Knight.2008.720p.BluRay.x264"
]

results = match_batch(torrents, show_progress=False)
for torrent, result in zip(torrents, results):
    print(f"{torrent[:40]:40} -> {result.title} ({result.year})")
print()

# Example 4: Using TorrentMatcher class with enricher
print("=" * 60)
print("Example 4: Using TorrentMatcher class")
print("=" * 60)

# Initialize with specific settings
matcher = TorrentMatcher(
    enable_enricher=False,  # Set to True if you have TMDB_API_KEY set
    verbose=False
)

result = matcher.match("Interstellar.2014.1080p", detail=True)
print(f"Title: {result['title']}")
print(f"Year: {result['year']}")
print(f"IMDB ID: {result.get('imdb_id')}")
if 'detail' in result:
    print(f"Parser: {result['detail'].get('parser_used')}")
    print(f"Confidence Level: {result['detail'].get('confidence_level')}")
print()

# Example 5: Detailed output with metadata
print("=" * 60)
print("Example 5: Detailed output")
print("=" * 60)

result = match("The.Avengers.2012.1080p", detail=True)
print(f"Title: {result['title']}")
print(f"IMDB ID: {result.get('imdb_id')}")
print(f"TMDB Match: {result.get('tmdb_match')}")

if 'detail' in result and result['detail'].get('genres'):
    print(f"Genres: {', '.join(result['detail']['genres'])}")
if 'detail' in result and result['detail'].get('overview'):
    print(f"Overview: {result['detail']['overview'][:100]}...")
