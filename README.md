# Torrent Content Detector

A robust Python module for identifying media content (movies/TV shows) from torrent names and file structures, using multiple parsing strategies with consensus-based confidence scoring.

## Features

- **Multi-Parser Consensus**: Runs GuessIt, PTN, ReBulk, and Regex parsers simultaneously, using weighted consensus for confidence
- **Automatic LLM Fallback**: When consensus confidence is low, automatically invokes LLM parser for a second attempt
- **Parser Selection**: Choose specific parsers to use (e.g., only PTN and LLM) instead of running all parsers
- **Granular Media Types**: Distinguishes between movies, TV episodes, season packs, and multi-season packs
- **TMDB Integration**: Validates parsed results and enriches with IMDB IDs, metadata, genres, ratings
- **Consensus Confidence**: Confidence based purely on parser agreement (not individual parser confidence)
- **Episode Extraction**: Automatically extracts individual episodes from season packs with missing episode detection
- **Dual Output Modes**: Simple output (default) or detailed output with full metadata
- **Batch Processing**: Efficient parallel processing for large datasets
- **Torrent File Parsing**: Decode `.torrent` files directly to capture names and file layouts
- **Dataset Pipeline**: Complete processing and analysis tools for torrent datasets

## Project Structure

```
torrent_match/
├── torrent_match/             # Public API
│   ├── __init__.py
│   ├── __main__.py
│   ├── match.py
│   └── cli.py
├── torrent_detector/          # Core detection module
│   ├── detector.py
│   ├── parsers/
│   ├── tmdb_validator.py
│   ├── tmdb_enricher.py
│   ├── episode_extractor.py
│   └── file_structure_detector.py
├── scripts/                   # Dataset processing scripts
│   ├── process_dataset.py
│   ├── analyse_dataset.py
│   └── test.py
├── examples/
├── tests/
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Installation

### From Source

```bash
cd torrent_match
pip install -e .
```

This will install the package and make the `torrent-match` CLI command available.

The project uses modern Python packaging with `pyproject.toml`.

### Requirements Only

```bash
pip install -r requirements.txt
```

## Quick Start

### Library API (Recommended)

The `torrent_match` module provides a clean, simple API for matching torrents:

```python
from torrent_match import match, match_batch, match_torrent_file, TorrentMatcher

# Quick match
result = match("The.Matrix.1999.1080p.BluRay.x264")
print(f"{result.title} ({result.year}) - {result.imdb_id}")

# Batch matching
results = match_batch([
    "Inception.2010.1080p",
    "Breaking.Bad.S05E14.720p"
])

# From a torrent file
torrent_result = match_torrent_file("/path/to/file.torrent")
print(f"{torrent_result.title} ({torrent_result.year}) - {torrent_result.media_type.value}")

# Use TorrentMatcher class for more control
matcher = TorrentMatcher(enable_enricher=True)
result = matcher.match("Interstellar.2014", detail=True)

# Use only specific parsers
result = match("Movie.2023", parsers=['ptn', 'guessit'])

# Use only LLM parser
result = match("ambiguous title", parsers=['llm'])
```

See `examples/simple_match.py` for more examples.

### Command Line Interface

```bash
# Identify a single torrent
torrent-match identify "The.Matrix.1999.1080p.BluRay.x264"

# Identify from a .torrent file
torrent-match identify --torrent-file /path/to/file.torrent

# Use specific parsers only
torrent-match identify "Movie.2023" --parsers "ptn,llm"

# Batch process from a file
torrent-match batch torrents.txt --output results.json

# Batch process with specific parsers
torrent-match batch torrents.txt --parsers "guessit,ptn" --output results.json

# Process a dataset
torrent-match process-dataset dataset.json --output processed.json

# Analyze results
torrent-match analyze processed.json --output analysis.json

# Run tests
torrent-match test --dataset dataset.json
```

### Basic Usage (Direct Module Access)

```python
from torrent_detector import TorrentContentDetector

# Initialize detector (with TMDB for IMDB ID recovery)
detector = TorrentContentDetector(tmdb_api_key="your_api_key")

# Identify content from torrent name
result = detector.identify("The.Matrix.1999.1080p.BluRay.x264-SPARKS")

# Simple output (default)
output = result.to_dict()
print(output)
# {
#   "imdb_id": "tt0133093",
#   "tmdb_id": 603,
#   "title": "The Matrix",
#   "year": 1999,
#   "media_type": "movie",
#   "medium": "MOVIE",
#   "confidence": 0.9,
#   "tmdb_match": true
# }

# Detailed output with full metadata
detailed = result.to_dict(detail=True)
print(detailed)
# Same as above, plus:
# {
#   ...
#   "detail": {
#     "parser_used": "Consensus(4)",
#     "confidence_level": "HIGH",
#     "overview": "...",
#     "genres": ["Action", "Science Fiction"],
#     "vote_average": 8.2,
#     "runtime": 136,
#     "consensus": {...},
#     "title_confidence": {...}
#   }
# }
```

### With TMDB API Key (Recommended)

```bash
export TMDB_API_KEY="your_tmdb_api_key"
```

```python
detector = TorrentContentDetector(tmdb_api_key="your_api_key")

# Now includes IMDB ID recovery and validation
result = detector.identify("Inception.2010.720p.BluRay.x264")
# result.imdb_id will be populated if found in TMDB
```

### With TMDB Enricher (Enhanced Media Info)

The enricher uses the local tmdb library to add comprehensive media information including cast, crew, genres, ratings, runtime, and more. It provides offline-capable lookups using a local cache.

```bash
export TMDB_API_KEY="your_tmdb_api_key"
```

```python
detector = TorrentContentDetector(
    tmdb_api_key="your_api_key",
    enable_enricher=True,  # Enable rich media info
    enricher_use_local_cache=True,  # Use offline cache
    enricher_min_popularity=10.0  # Cache items with popularity >= 10
)

result = detector.identify("The.Dark.Knight.2008.1080p.BluRay.x264")

# Now includes extensive metadata
print(f"Overview: {result.metadata.get('overview')}")
print(f"Genres: {result.metadata.get('genres')}")
print(f"Runtime: {result.metadata.get('runtime')} minutes")
print(f"Cast: {[actor['name'] for actor in result.metadata.get('cast', [])]}")
print(f"Director: {[c['name'] for c in result.metadata.get('crew', []) if c['job'] == 'Director']}")
print(f"Rating: {result.metadata.get('vote_average')}/10")
print(f"Budget: ${result.metadata.get('budget'):,}")
print(f"Revenue: ${result.metadata.get('revenue'):,}")
```

**Enricher Benefits:**
- **Offline-capable**: Uses local SQLite cache for popular media
- **Rich metadata**: Cast, crew, genres, ratings, runtime, budget, revenue
- **Poster downloads**: Can download and cache poster images
- **Fuzzy search**: Better title matching using local index
- **Fast**: Cached lookups are instant

**Download posters:**

```python
# Download poster for a result
poster_path = detector.tmdb_enricher.download_poster(result)
print(f"Poster saved to: {poster_path}")
```

### With LLM Fallback

The LLM parser is automatically used when the consensus confidence is LOW or VERY_LOW, providing a second chance for difficult or ambiguous torrent names.

```bash
# For OpenRouter (recommended, cheaper)
export LLM_API_KEY="your_openrouter_api_key"
export LLM_API_ENDPOINT="https://openrouter.ai/api/v1"
export LLM_MODEL="google/gemini-2.0-flash-exp"

# For OpenAI
export LLM_API_KEY="your_openai_api_key"
export LLM_API_ENDPOINT="https://api.openai.com/v1"
export LLM_MODEL="gpt-3.5-turbo"
```

```python
detector = TorrentContentDetector(
    llm_api_key="your_llm_key",
    llm_api_endpoint="https://openrouter.ai/api/v1",
    llm_model="google/gemini-2.0-flash-exp",
    use_llm_fallback=True  # Enable automatic LLM fallback
)

# LLM will be automatically invoked if regular parsers have low confidence
result = detector.identify("matrix 1999 movie")

# You can also use only the LLM parser
detector_llm_only = TorrentContentDetector(
    llm_api_key="your_llm_key",
    llm_api_endpoint="https://openrouter.ai/api/v1",
    llm_model="google/gemini-2.0-flash-exp",
    parsers=['llm']  # Only use LLM parser
)
result = detector_llm_only.identify("ambiguous title")
```

### Dataset Processing Pipeline

Process large torrent datasets and generate comprehensive analysis:

```bash
# Step 1: Process dataset (generates id/input/output structure)
python scripts/process_dataset.py \
  --dataset dataset.json \
  --output /tmp/processed_dataset.json \
  --limit 1000

# Step 2: Analyze processed results
python scripts/analyse_dataset.py \
  --input /tmp/processed_dataset.json \
  --output /tmp/analysis_results.json
```

**Output Structure:**

```json
{
  "id": "sample_id_here",
  "input": {
    "name": "Torrent.Name.S01E01.720p",
    "size": 1234567890,
    "imdb_id": "tt1234567",
    "type": "tv",
    "files": [...]
  },
  "output": {
    "imdb_id": "tt1234567",
    "title": "Show Name",
    "year": 2020,
    "media_type": "tv_episode",
    "medium": "TV",
    "confidence": 0.9,
    "season": 1,
    "episode": 1,
    "detail": {
      "parser_used": "Consensus(4)",
      "overview": "...",
      "genres": ["Drama"],
      "episodes": [...],
      "episode_summary": {...}
    }
  }
}
```

**Analysis Output:**

The analysis script generates comprehensive metrics including:
- Detection accuracy (IMDB match rate, type match rate)
- File structure analysis
- Episode extraction statistics
- Parser performance metrics
- Confidence distribution
- Discrepancy detection

## Parser Architecture

The module uses a **consensus-based** approach rather than sequential fallback:

### Active Parsers
1. **GuessIt** (weight: 1.0) - Most reliable for title extraction
2. **PTN** (weight: 0.8) - Very good secondary parser
3. **ReBulk** (weight: 0.6) - Decent pattern matching
4. **Regex** (weight: 0.2) - Basic fallback
5. **LLM** (weight: 0.5) - Optional AI-powered fallback for edge cases

### Consensus System

All parsers run simultaneously. The final result is determined by:

- **Title Selection**: Weighted voting system based on parser trust scores
- **Confidence Scoring**: Based purely on parser agreement (not individual parser confidence)
  - High agreement (all parsers agree) = HIGH confidence
  - Good agreement (most parsers agree) = MEDIUM confidence
  - Low agreement = LOW confidence
- **Media Type**: Most common type across parsers (preserves granular types like `tv_episode`)
- **TMDB Validation**: Preserves specific TV media types (episode/season/multi-season)

### Automatic LLM Fallback

When the consensus confidence is **LOW** or **VERY_LOW**, the system automatically invokes the LLM parser (if available and configured) as a fallback. The LLM parser's output is used directly, replacing the low-confidence consensus result. This ensures difficult or ambiguous torrent names get a second chance at accurate parsing.

To enable automatic LLM fallback:
- Set `use_llm_fallback=True` when initializing the detector
- Provide LLM API credentials via environment variables or constructor parameters
- The LLM will only be invoked when regular parsers produce low-confidence results

### Parser Selection

You can specify which parsers to use instead of running all of them:

```python
from torrent_match import match, TorrentMatcher

# Use only specific parsers
result = match("Movie.2023", parsers=['ptn', 'guessit'])

# Use only LLM parser
result = match("ambiguous title", parsers=['llm'])

# Or configure at matcher level
matcher = TorrentMatcher(parsers=['guessit', 'ptn'])
result = matcher.match("Movie.2023")
```

Valid parser names: `'guessit'`, `'ptn'`, `'rebulk'`, `'regex'`, `'llm'`

## Library API Reference

### `match()` - Quick single match

```python
from torrent_match import match

result = match("The.Matrix.1999.1080p")
# Returns MediaIdentification object
print(result.title, result.year, result.imdb_id)
```

### `match_batch()` - Batch matching

```python
from torrent_match import match_batch

results = match_batch([
    "Inception.2010",
    "Breaking.Bad.S05E14"
], max_workers=10)
```

### `TorrentMatcher` - Full control

```python
from torrent_match import TorrentMatcher

# Create matcher with custom settings
matcher = TorrentMatcher(
    enable_enricher=True,
    verbose=True,
    parsers=['guessit', 'ptn', 'llm']  # Optional: specify parsers to use
)

# Match with files
result = matcher.match(
    "Breaking.Bad.S01",
    files=["episode1.mkv", "episode2.mkv"]
)

# Get detailed output
detailed = matcher.match("Inception.2010", detail=True)
print(detailed['detail']['genres'])
```

## Command Line Interface Reference

### `identify` - Match a single torrent

```bash
torrent-match identify "The.Matrix.1999.1080p" --detail --json

# Use only specific parsers
torrent-match identify "Movie.2023" --parsers "ptn,llm"

# Use only LLM parser
torrent-match identify "ambiguous title" --parsers "llm"
```

Options:
- `--files FILE [FILE ...]` - Specify file paths
- `--detail` - Show detailed metadata
- `--json` - Output as JSON
- `--enricher` - Enable TMDB enricher
- `--parsers "parser1,parser2"` - Comma-separated list of parsers (guessit, ptn, rebulk, regex, llm)

### `batch` - Process multiple torrents

```bash
# Create a file with one torrent name per line
echo "The.Matrix.1999.1080p" > torrents.txt
echo "Inception.2010.720p" >> torrents.txt

torrent-match batch torrents.txt --output results.json --workers 10

# Use only specific parsers for batch processing
torrent-match batch torrents.txt --parsers "guessit,ptn" --output results.json
```

Options:
- `-o, --output FILE` - Output JSON file
- `--detail` - Include detailed metadata
- `--workers N` - Number of parallel workers
- `--enricher` - Enable TMDB enricher
- `--parsers "parser1,parser2"` - Comma-separated list of parsers (guessit, ptn, rebulk, regex, llm)

### `process-dataset` - Process dataset

```bash
torrent-match process-dataset dataset.json \
  --output /tmp/processed.json \
  --limit 1000 \
  --save-interval 100
```

### `analyze` - Analyze results

```bash
torrent-match analyze processed.json \
  --output analysis.json \
  --min-confidence 0.8
```

### `test` - Run tests

```bash
torrent-match test --dataset dataset.json --limit 100
```

## Testing

Run the comprehensive test suite:

```bash
python scripts/test.py
# or
torrent-match test
```

## Quick Example

```python
from torrent_detector import TorrentContentDetector

# Initialize with TMDB
detector = TorrentContentDetector(tmdb_api_key="your_key")

# Process a torrent
result = detector.identify("Breaking.Bad.S05E14.720p.HDTV.x264-KILLERS")

# Simple output
print(result.to_dict())
# {"imdb_id": "tt0959621", "title": "Breaking Bad", "year": 2008,
#  "media_type": "tv_episode", "season": 5, "episode": 14, "confidence": 0.9}

# Detailed output with full metadata
print(result.to_dict(detail=True))
# Includes parser consensus, TMDB metadata, genres, ratings, etc.
```

## Configuration

### Environment Variables

```bash
TMDB_API_KEY=your_tmdb_api_key_here                          # Required for IMDB recovery and enricher
LLM_API_KEY=your_llm_api_key_here                            # LLM API key (OpenRouter or OpenAI)
LLM_API_ENDPOINT=your_llm_endpoint                           # LLM endpoint (OpenRouter or OpenAI)
LLM_MODEL=your_llm_model                                     # LLM model (e.g., google/gemini-2.0-flash-exp)
CACHE_DB_PATH=/tmp/torrent_interpret.db                      # redislite cache database path
TMDB_ENRICHER_CACHE=/tmp/torrent_match/tmdb.sqlite  # SQLite cache for enricher (optional)
```

### Advanced Usage

```python
# With all features enabled
detector = TorrentContentDetector(
    tmdb_api_key="your_tmdb_key",
    llm_api_key="your_llm_key",
    llm_api_endpoint="https://openrouter.ai/api/v1",
    llm_model="google/gemini-2.0-flash-exp",
    cache_db_path="/tmp/torrent_interpret.db",
    use_llm_fallback=True,  # Enables automatic LLM fallback for low confidence
    enable_caching=True,
    enable_enricher=True,  # Enable rich media info
    enricher_cache_path="/tmp/torrent_match/tmdb.sqlite",
    enricher_use_local_cache=True,
    enricher_min_popularity=10.0,
    parsers=['guessit', 'ptn', 'llm']  # Optional: specify which parsers to use
)

# Batch processing with parallel execution
results = detector.identify_batch([
    ("Movie.Name.2023.1080p", files1),
    ("TV.Show.S01E01", files2),
    # ... more torrents
], max_workers=10)

# Use TorrentMatcher with parser selection
matcher = TorrentMatcher(
    parsers=['ptn', 'llm'],  # Only use PTN and LLM parsers
    use_llm_fallback=True    # LLM will be used automatically for low confidence
)
result = matcher.match("ambiguous.movie.title")
```

## Media Types

The detector provides granular media type classification:

- **`movie`** - Single movie file
- **`tv_episode`** - Single TV episode (e.g., S01E05)
- **`tv_season`** - Complete season pack (multiple episodes from one season)
- **`tv_multi_season`** - Multiple seasons in one torrent
- **`tv_show`** - Generic TV content (when specific type cannot be determined)

The `medium` field provides simplified classification: `"TV"` or `"MOVIE"`

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Torrent Name  │    │  File Structure  │    │   Pre-process   │
│   + Files       │───▶│   Analysis       │───▶│   & Normalize   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                        ┌────────────────────────────────────────┐
                        │      Multi-Parser Consensus            │
                        │  ┌──────┐  ┌──────┐  ┌──────┐         │
                        │  │GuessIt│ │ PTN  │  │ReBulk│  ...    │
                        │  └──────┘  └──────┘  └──────┘         │
                        │                                        │
                        │  Weighted Voting → Confidence Score   │
                        └────────────────────────────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   TMDB Lookup   │    │  Episode         │    │   Final Result  │
│   & Enrichment  │───▶│  Extraction      │───▶│   + Metadata    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Performance

- **Single torrent**: 10-300ms processing time
- **Batch processing**: 20-50 torrents/second with parallel execution
- **Memory usage**: ~10-50MB for typical operations
- **TMDB API calls**: ~0.1 calls per torrent (with caching)

## Typical Workflow

### For Library Usage

```python
from torrent_detector import TorrentContentDetector

detector = TorrentContentDetector(tmdb_api_key="your_key")
result = detector.identify("Torrent.Name.2020.1080p")

# Use simple output
print(result.to_dict())

# Or get detailed metadata
print(result.to_dict(detail=True))
```

### For Dataset Processing

```bash
# 1. Process your dataset
python scripts/process_dataset.py \
  --dataset dataset.json \
  --output /tmp/processed.json \
  --limit 1000

# 2. Analyze the results
python scripts/analyse_dataset.py \
  --input /tmp/processed.json \
  --output /tmp/analysis.json

# 3. Review metrics
cat /tmp/analysis.json | jq '.detection_accuracy'
```

## Documentation

- **README.md** (this file) - Overview and quick start
- **USAGE.md** - Detailed usage guide with examples
- **dataset.md** - Dataset format specification
