# Torrent Content Detector - Detailed Usage Guide

Complete guide to using the Torrent Content Detector for media identification and dataset processing.

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
    cache_db_path: str = "/tmp/torrent_interpret.db",
    use_llm_fallback: bool = False,
    enable_caching: bool = True
)
```

**Methods:**
- `identify(name, files=None) -> MediaIdentification`
- `identify_batch(items, max_workers=5) -> List[MediaIdentification]`

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

1. Always use TMDB API key for IMDB ID recovery
2. Use `detail=True` when you need full metadata
3. Process large datasets with periodic saving
4. Check confidence levels before trusting results
5. Run analysis after processing for quality metrics

## Complete Example

```python
from torrent_detector import TorrentContentDetector

# Initialize detector
detector = TorrentContentDetector(tmdb_api_key="your_api_key")

# Process a movie
movie = detector.identify("The.Matrix.1999.1080p.BluRay.x264-SPARKS")
print(f"Movie: {movie.title} ({movie.year})")
print(f"IMDB: {movie.imdb_id}")
print(f"Confidence: {movie.confidence.name}")

# Process a TV episode
episode = detector.identify("Breaking.Bad.S05E14.720p.HDTV.x264-KILLERS")
print(f"\nTV Show: {episode.title} ({episode.year})")
print(f"Season {episode.season}, Episode {episode.episode}")
print(f"Type: {episode.media_type.value}")

# Get detailed output
detailed = episode.to_dict(detail=True)
print(f"\nGenres: {detailed['detail']['genres']}")
print(f"Overview: {detailed['detail']['overview'][:100]}...")
```
