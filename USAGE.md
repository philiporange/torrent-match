# Torrent Content Detector - Detailed Usage Guide

Complete guide to using the Torrent Content Detector for media identification and dataset processing.

## New Features

- **Automatic LLM Fallback**: When consensus confidence is low, the system automatically invokes the LLM parser for a second attempt
- **Parser Selection**: Choose specific parsers to use (e.g., only PTN and LLM) instead of running all parsers

## Available Tools

The project includes three main scripts:

1. **`torrent_detector` module** - Python library for media detection
   - Use in your own Python code
   - Provides `TorrentContentDetector` class

2. **`process_dataset.py`** - Process torrent datasets
   - Reads `dataset.json` with torrent metadata
   - Outputs id/input/output structure with detection results
   - Supports batch processing with periodic saves

3. **`analyse_dataset.py`** - Analyze processed datasets
   - Generates comprehensive statistics and metrics
   - Detects discrepancies and quality issues
   - Provides parser performance analysis

4. **`test.py`** - Test suite
   - Validates detector functionality
   - Tests all parser implementations

## Table of Contents

- [Basic Detection](#basic-detection)
- [Parsing Torrent Files](#parsing-torrent-files)
- [Output Modes](#output-modes)
- [Media Types](#media-types)
- [Confidence Scoring](#confidence-scoring)
- [Automatic LLM Fallback](#automatic-llm-fallback)
- [Parser Selection](#parser-selection)
- [TMDB Integration](#tmdb-integration)
- [Dataset Processing](#dataset-processing)
- [Dataset Analysis](#dataset-analysis)
- [API Reference](#api-reference)

## Basic Detection

### Simple Movie Detection

```python
from torrent_detector import TorrentContentDetector

detector = TorrentContentDetector(tmdb_api_key="your_api_key")
result = detector.identify("The.Matrix.1999.1080p.BluRay.x264-SPARKS")

print(result.title)          # "The Matrix"
print(result.year)           # 1999
print(result.media_type)     # MediaType.MOVIE
print(result.imdb_id)        # "tt0133093"
print(result.confidence)     # ConfidenceLevel.HIGH
```

### TV Show Detection

```python
# Single episode
result = detector.identify("Breaking.Bad.S05E14.720p.HDTV.x264-KILLERS")
print(result.media_type)     # MediaType.TV_EPISODE
print(result.season)         # 5
print(result.episode)        # 14

# Season pack
result = detector.identify("Game.of.Thrones.S08.1080p.BluRay.x264-ROVERS")
print(result.media_type)     # MediaType.TV_SEASON
print(result.season)         # 8
```

## Parsing Torrent Files

The `torrent_match` package can now read `.torrent` files directly, exposing the
declared display name and file layout so matching automatically benefits from
the bundled file structure.

```python
from torrent_match import match_torrent_file, parse_torrent_file

# Identify a torrent using the bundled metadata
result = match_torrent_file("/path/to/file.torrent")
print(result.title)
print(result.media_type)

# Access the raw parsed contents
parsed = parse_torrent_file("/path/to/file.torrent")
print(parsed.name)
print(parsed.files[0]["path"], parsed.files[0]["length"])
```

CLI users can achieve the same with:

```bash
torrent-match identify --torrent-file /path/to/file.torrent --detail
```

## Output Modes

### Simple Mode (Default)

```python
result = detector.identify("The.Dark.Knight.2008.1080p")
output = result.to_dict()  # or result.to_dict(detail=False)
```

Output:
```json
{
  "imdb_id": "tt0468569",
  "tmdb_id": 155,
  "title": "The Dark Knight",
  "year": 2008,
  "media_type": "movie",
  "medium": "MOVIE",
  "confidence": 0.9,
  "tmdb_match": true
}
```

### Detailed Mode

```python
output = result.to_dict(detail=True)
```

Adds a `detail` section with full metadata:
- Parser consensus information
- Title confidence voting details
- TMDB metadata (overview, genres, ratings, runtime)
- Episode extraction (for TV content)

## Media Types

| Type | Description |
|------|-------------|
| `movie` | Single movie |
| `tv_episode` | Single TV episode (S01E05) |
| `tv_season` | Complete season pack |
| `tv_multi_season` | Multiple seasons |
| `tv_show` | Generic TV content |

The `medium` field provides simplified "TV" or "MOVIE" classification.

## Confidence Scoring

Confidence is based purely on parser agreement:

```python
print(result.confidence_value)  # 0.9 (numeric)
print(result.confidence)        # ConfidenceLevel.HIGH
```

**Levels:**
- HIGH (0.85-1.0): All/most parsers agree
- MEDIUM (0.70-0.84): Good agreement
- LOW (0.50-0.69): Some disagreement
- VERY_LOW (<0.50): Significant disagreement

## Automatic LLM Fallback

When the consensus confidence is **LOW** or **VERY_LOW**, the system automatically invokes the LLM parser (if configured) as a fallback. This provides a second chance for difficult or ambiguous torrent names.

### Enabling LLM Fallback

```python
from torrent_detector import TorrentContentDetector

# Initialize with LLM fallback enabled
detector = TorrentContentDetector(
    tmdb_api_key="your_tmdb_key",
    llm_api_key="your_llm_key",
    llm_api_endpoint="https://openrouter.ai/api/v1",
    llm_model="google/gemini-2.0-flash-exp",
    use_llm_fallback=True  # Enable automatic fallback
)

# LLM will be automatically invoked if regular parsers have low confidence
result = detector.identify("matrix 1999 movie")

# Check if LLM fallback was used
if result.metadata.get('llm_fallback'):
    print("LLM fallback was used!")
    original = result.metadata['original_confidence']
    print(f"Original confidence: {original['level']} ({original['score']:.2f})")
```

### Using TorrentMatcher with LLM Fallback

```python
from torrent_match import TorrentMatcher

matcher = TorrentMatcher(
    use_llm_fallback=True,  # Enable automatic LLM fallback
    verbose=True
)

result = matcher.match("ambiguous.torrent.name")
```

### How It Works

1. All non-LLM parsers run and produce a consensus result
2. Confidence is calculated based on parser agreement
3. If confidence is LOW or VERY_LOW:
   - LLM parser is automatically invoked
   - LLM result replaces the low-confidence consensus
   - Original confidence is preserved in metadata
4. If LLM succeeds, result is validated with TMDB (if available)
5. Final result has MEDIUM confidence (trusting LLM moderately)

### Environment Variables

```bash
# For OpenRouter (recommended, cheaper)
export LLM_API_KEY="your_openrouter_api_key"
export LLM_API_ENDPOINT="https://openrouter.ai/api/v1"
export LLM_MODEL="google/gemini-2.0-flash-exp"

# For OpenAI
export LLM_API_KEY="your_openai_api_key"
export LLM_API_ENDPOINT="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o-mini"

# Enable LLM fallback globally
export USE_LLM_FALLBACK=true
```

## Parser Selection

You can specify which parsers to use instead of running all of them. This is useful for:
- Testing specific parsers
- Faster processing with fewer parsers
- Using only the most reliable parsers
- Using only the LLM parser for difficult cases

### Available Parsers

- **`guessit`** - Most reliable for title extraction (weight: 1.0)
- **`ptn`** - Very good secondary parser (weight: 0.8)
- **`rebulk`** - Decent pattern matching (weight: 0.6)
- **`regex`** - Basic fallback parser (weight: 0.2)
- **`llm`** - AI-powered parser for edge cases (weight: 0.5)

### Using Specific Parsers

```python
from torrent_match import match, TorrentMatcher

# Use only PTN and GuessIt
result = match("Movie.2023.1080p", parsers=['ptn', 'guessit'])

# Use only LLM parser
result = match("ambiguous title", parsers=['llm'])

# Use GuessIt, ReBulk, and Regex
result = match("Show.S01E01", parsers=['guessit', 'rebulk', 'regex'])
```

### With TorrentMatcher

```python
from torrent_match import TorrentMatcher

# Create matcher with specific parsers
matcher = TorrentMatcher(parsers=['guessit', 'ptn'])

# All matches use only these parsers
result1 = matcher.match("Movie.2023")
result2 = matcher.match("Show.S01E01")

# Batch processing with specific parsers
results = matcher.match_batch([
    "Movie1.2023",
    "Movie2.2022"
])
```

### With TorrentContentDetector

```python
from torrent_detector import TorrentContentDetector

# Create detector with specific parsers
detector = TorrentContentDetector(
    tmdb_api_key="your_key",
    parsers=['guessit', 'ptn', 'llm']
)

result = detector.identify("Torrent.Name.2023")
```

### Command Line

```bash
# Use only PTN parser
torrent-match identify "Movie.2023" --parsers "ptn"

# Use PTN and LLM
torrent-match identify "Movie.2023" --parsers "ptn,llm"

# Batch processing with specific parsers
torrent-match batch torrents.txt --parsers "guessit,ptn" --output results.json
```

### Best Practices

1. **Default (all parsers)**: Best for accuracy, uses consensus
2. **GuessIt + PTN**: Fast and reliable for most torrents
3. **LLM only**: For very difficult/ambiguous names (requires API key)
4. **PTN + LLM**: Good balance of speed and handling edge cases

## TMDB Integration

```python
detector = TorrentContentDetector(tmdb_api_key="your_api_key")
result = detector.identify("Inception.2010")

print(result.imdb_id)       # "tt1375666"
print(result.tmdb_id)       # 27205
print(result.tmdb_match)    # True
```

Metadata in detailed mode:
```python
output = result.to_dict(detail=True)
metadata = output["detail"]

print(metadata["overview"])
print(metadata["genres"])
print(metadata["vote_average"])
print(metadata["runtime"])
```

## Dataset Processing

### Process Dataset

```bash
python process_dataset.py \
  --dataset dataset.json \
  --output /tmp/processed_dataset.json \
  --limit 1000 \
  --save-interval 100
```

**Input format:**
```json
[
  {
    "name": "Torrent.Name.2020.1080p",
    "size": 8589934592,
    "imdb_id": "tt1234567",
    "type": "movie",
    "files": [...],
    "sample_id": "unique_id"
  }
]
```

**Output format:**
```json
{
  "id": "unique_id",
  "input": { /* original dataset entry */ },
  "output": { /* detection result with detail=True */ }
}
```

## Dataset Analysis

```bash
python analyse_dataset.py \
  --input /tmp/processed_dataset.json \
  --output /tmp/analysis_results.json
```

**Analysis metrics:**
- Detection accuracy (IMDB match rate, type match rate)
- File structure analysis
- Episode extraction statistics
- Parser performance
- Confidence distribution
- Discrepancy detection

## API Reference

### TorrentContentDetector

```python
detector = TorrentContentDetector(
    tmdb_api_key: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    llm_api_endpoint: Optional[str] = None,
    llm_model: Optional[str] = None,
    cache_db_path: str = "/tmp/torrent_interpret.db",
    use_llm_fallback: bool = False,
    enable_caching: bool = True,
    enable_enricher: bool = False,
    enricher_cache_path: str = "/tmp/torrent_match/tmdb.sqlite",
    enricher_use_local_cache: bool = True,
    enricher_min_popularity: float = 10.0,
    parsers: Optional[List[str]] = None
)
```

**Parameters:**
- `tmdb_api_key`: TMDB API key for validation and IMDB lookup
- `llm_api_key`: LLM API key (OpenRouter or OpenAI)
- `llm_api_endpoint`: LLM API endpoint URL
- `llm_model`: LLM model name to use
- `cache_db_path`: Path to cache database file
- `use_llm_fallback`: Enable automatic LLM fallback for low confidence (default: False)
- `enable_caching`: Enable result caching (default: True)
- `enable_enricher`: Enable TMDB enricher for detailed metadata (default: False)
- `enricher_cache_path`: Path to enricher cache database
- `enricher_use_local_cache`: Use local cache for enricher (default: True)
- `enricher_min_popularity`: Minimum popularity for enricher caching (default: 10.0)
- `parsers`: Optional list of parser names to use (default: all parsers)
  - Valid values: `['guessit', 'ptn', 'rebulk', 'regex', 'llm']`

**Methods:**
- `identify(name, files=None) -> MediaIdentification`
- `identify_batch(items, max_workers=5) -> List[MediaIdentification]`

### TorrentMatcher

```python
from torrent_match import TorrentMatcher

matcher = TorrentMatcher(
    tmdb_api_key: Optional[str] = None,
    enable_enricher: bool = False,
    use_llm_fallback: bool = False,
    llm_api_key: Optional[str] = None,
    llm_api_endpoint: Optional[str] = None,
    llm_model: Optional[str] = None,
    cache_db_path: Optional[str] = None,
    enricher_cache_path: Optional[str] = None,
    verbose: bool = False,
    parsers: Optional[List[str]] = None
)
```

**Parameters:**
- `tmdb_api_key`: TMDB API key (falls back to TMDB_API_KEY env var)
- `enable_enricher`: Enable TMDB enricher for detailed metadata
- `use_llm_fallback`: Enable automatic LLM fallback for low confidence
- `llm_api_key`: LLM API key (falls back to LLM_API_KEY env var)
- `llm_api_endpoint`: LLM API endpoint (falls back to LLM_API_ENDPOINT env var)
- `llm_model`: LLM model name (falls back to LLM_MODEL env var)
- `cache_db_path`: Path to cache database
- `enricher_cache_path`: Path to enricher cache database
- `verbose`: Enable verbose logging
- `parsers`: Optional list of parser names to use (default: all parsers)

**Methods:**
- `match(torrent_name, files=None, detail=False) -> MediaIdentification | Dict`
- `match_batch(torrents, max_workers=5, show_progress=True, detail=False) -> List`
- `match_torrent_file(torrent_file, detail=False) -> MediaIdentification | Dict`
- `match_from_sample(sample, detail=False) -> MediaIdentification | Dict`

### Convenience Functions

```python
from torrent_match import match, match_batch, match_torrent_file

# Quick single match
result = match(
    torrent_name: str,
    files: Optional[List] = None,
    detail: bool = False,
    parsers: Optional[List[str]] = None
)

# Batch matching
results = match_batch(
    torrents: List[str] | List[Tuple[str, List]],
    max_workers: int = 5,
    show_progress: bool = True,
    detail: bool = False,
    parsers: Optional[List[str]] = None
)

# Match from .torrent file
result = match_torrent_file(
    torrent_file: str | Path,
    detail: bool = False,
    parsers: Optional[List[str]] = None
)
```

### MediaIdentification

**Properties:**
- `imdb_id`, `tmdb_id`, `title`, `year`
- `media_type` (MediaType enum)
- `season`, `episode` (for TV content)
- `confidence` (ConfidenceLevel enum)
- `confidence_value` (0.0-1.0)
- `medium` ("TV" or "MOVIE")
- `tmdb_match` (bool)

**Methods:**
- `to_dict(detail=False) -> Dict[str, Any]`

## Environment Variables

```bash
export TMDB_API_KEY="your_tmdb_api_key"
export LLM_API_KEY="your_llm_key"
export LLM_API_ENDPOINT="https://openrouter.ai/api/v1"
export LLM_MODEL="google/gemini-2.0-flash-exp"
```

## Best Practices

1. **Always use TMDB API key** for IMDB ID recovery and validation
2. **Enable LLM fallback** (`use_llm_fallback=True`) for better handling of difficult cases
3. **Use parser selection** to optimize for your use case:
   - Default (all parsers): Best accuracy, consensus-based
   - GuessIt + PTN: Fast and reliable for most torrents
   - LLM only: For very ambiguous names
   - PTN + LLM: Balance of speed and edge case handling
4. **Use `detail=True`** when you need full metadata, genres, and parser consensus info
5. **Process large datasets** with periodic saving and batch processing
6. **Check confidence levels** before trusting results:
   - HIGH/MEDIUM: Generally trustworthy
   - LOW/VERY_LOW: May need manual verification (unless LLM fallback succeeded)
7. **Run analysis after processing** for quality metrics and discrepancy detection
8. **Enable enricher** for comprehensive media metadata (cast, crew, ratings, etc.)
9. **Use verbose mode** during development to see parser decisions and confidence scores

## Complete Example

```python
from torrent_detector import TorrentContentDetector
from torrent_match import match, TorrentMatcher

# Example 1: Basic usage with all features
detector = TorrentContentDetector(
    tmdb_api_key="your_tmdb_key",
    llm_api_key="your_llm_key",
    llm_api_endpoint="https://openrouter.ai/api/v1",
    llm_model="google/gemini-2.0-flash-exp",
    use_llm_fallback=True,  # Enable automatic LLM fallback
    enable_enricher=True,   # Enable rich metadata
    parsers=['guessit', 'ptn', 'llm']  # Use specific parsers
)

# Process a movie
movie = detector.identify("The.Matrix.1999.1080p.BluRay.x264-SPARKS")
print(f"Movie: {movie.title} ({movie.year})")
print(f"IMDB: {movie.imdb_id}")
print(f"Confidence: {movie.confidence.name} ({movie.confidence_value:.2f})")

# Check if LLM fallback was used
if movie.metadata.get('llm_fallback'):
    print("  → LLM fallback was used!")
    original = movie.metadata['original_confidence']
    print(f"  → Original confidence: {original['level']} ({original['score']:.2f})")

# Process a TV episode
episode = detector.identify("Breaking.Bad.S05E14.720p.HDTV.x264-KILLERS")
print(f"\nTV Show: {episode.title} ({episode.year})")
print(f"Season {episode.season}, Episode {episode.episode}")
print(f"Type: {episode.media_type.value}")
print(f"Confidence: {episode.confidence.name}")

# Get detailed output
detailed = episode.to_dict(detail=True)
print(f"\nGenres: {detailed['detail']['genres']}")
print(f"Overview: {detailed['detail']['overview'][:100]}...")
if 'cast' in detailed['detail']:
    print(f"Cast: {[actor['name'] for actor in detailed['detail']['cast'][:3]]}")

# Example 2: Quick matching with parser selection
print("\n--- Quick Matching ---")

# Use only PTN and GuessIt for fast matching
result = match("Inception.2010.1080p", parsers=['ptn', 'guessit'])
print(f"Title: {result.title}, Year: {result.year}")

# Use only LLM for difficult case
result_llm = match("matrix 1999 movie", parsers=['llm'])
print(f"LLM Result: {result_llm.title} ({result_llm.year})")

# Example 3: Batch processing with automatic LLM fallback
print("\n--- Batch Processing ---")

matcher = TorrentMatcher(
    use_llm_fallback=True,
    parsers=['guessit', 'ptn', 'llm'],
    verbose=True
)

torrents = [
    "The.Dark.Knight.2008.1080p",
    "Breaking.Bad.S01E01.720p",
    "ambiguous.movie.title.2023"
]

results = matcher.match_batch(torrents, max_workers=3, show_progress=True)

for torrent, result in zip(torrents, results):
    print(f"\n{torrent}")
    print(f"  → {result.title} ({result.year})")
    print(f"  → Confidence: {result.confidence.name}")
    print(f"  → Parser: {result.parser_used}")
    if result.metadata.get('llm_fallback'):
        print(f"  → LLM fallback was used!")
```
