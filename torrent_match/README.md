# torrent_match Package

This package provides a clean, simple API for matching torrent names to their corresponding media content (movies and TV shows).

## What's in this package?

- **`match.py`** - Simple matching API with convenience functions
- **`cli.py`** - Command-line interface for all features
- **`__init__.py`** - Package exports

## Quick Start

### As a Library

```python
from torrent_match import match, match_batch, TorrentMatcher

# Quick match
result = match("The.Matrix.1999.1080p")
print(f"{result.title} ({result.year}) - {result.imdb_id}")

# Batch matching
results = match_batch(["Inception.2010", "Breaking.Bad.S05E14"])

# Use TorrentMatcher class for more control
matcher = TorrentMatcher(enable_enricher=True)
result = matcher.match("Interstellar.2014", detail=True)
```

### As a CLI

After installing the package:

```bash
# Identify a torrent
torrent-match identify "The.Matrix.1999.1080p"

# Process multiple torrents
torrent-match batch torrents.txt --output results.json

# Process a dataset
torrent-match process-dataset dataset.json
```

## Key Features

- **Simple API**: Just `match()` and you're done
- **Batch Processing**: Process thousands of torrents in parallel
- **Detailed Metadata**: Get IMDB IDs, genres, ratings, cast, and more
- **CLI Interface**: All features available from command line
- **Environment-based Config**: Uses TMDB_API_KEY and other env vars automatically

## API Functions

### `match(torrent_name, files=None, detail=False)`

Match a single torrent to its media content.

**Arguments:**
- `torrent_name` (str): The torrent name to match
- `files` (list, optional): List of file paths or file info dicts
- `detail` (bool): Return detailed output dict instead of MediaIdentification object

**Returns:** `MediaIdentification` object or dict

### `match_batch(torrents, max_workers=5, show_progress=True, detail=False)`

Match multiple torrents in parallel.

**Arguments:**
- `torrents` (list): List of torrent names or (name, files) tuples
- `max_workers` (int): Maximum parallel workers
- `show_progress` (bool): Show progress during processing
- `detail` (bool): Return detailed output dicts

**Returns:** List of `MediaIdentification` objects or dicts

### `TorrentMatcher` Class

High-level interface for torrent content matching with full control over configuration.

**Constructor Arguments:**
- `tmdb_api_key` (str, optional): TMDB API key
- `enable_enricher` (bool): Enable TMDB enricher for detailed metadata
- `use_llm_fallback` (bool): Use LLM parser as fallback
- `llm_api_key` (str, optional): LLM API key
- `llm_api_endpoint` (str, optional): LLM API endpoint
- `llm_model` (str, optional): LLM model name
- `cache_db_path` (str, optional): Path to cache database
- `enricher_cache_path` (str, optional): Path to enricher cache
- `verbose` (bool): Enable verbose logging

**Methods:**
- `match(torrent_name, files=None, detail=False)` - Match single torrent
- `match_batch(torrents, max_workers=5, show_progress=True, detail=False)` - Match multiple torrents
- `match_from_sample(sample, detail=False)` - Match from DatasetSample object

## Environment Variables

The module automatically reads these environment variables:

- `TMDB_API_KEY` - TMDB API key for validation and enrichment
- `LLM_API_KEY` - LLM API key for fallback parsing
- `LLM_API_ENDPOINT` - LLM API endpoint (e.g., OpenRouter or OpenAI)
- `LLM_MODEL` - LLM model to use
- `USE_LLM_FALLBACK` - Enable LLM fallback (1/true/yes/on)
- `VERBOSE` - Enable verbose logging (1/true/yes/on)

## Examples

See `../examples/simple_match.py` for complete examples.

## CLI Commands

After installing the package, use the `torrent-match` command:

```bash
# Get help
torrent-match --help

# Identify a torrent
torrent-match identify "The.Matrix.1999.1080p" --detail

# Batch process
torrent-match batch torrents.txt --output results.json --workers 10

# Process dataset
torrent-match process-dataset dataset.json --output processed.json

# Analyze results
torrent-match analyze processed.json --output analysis.json

# Run tests
torrent-match test --dataset dataset.json
```

## Architecture

This package is a high-level wrapper around the `torrent_detector` module, which contains the core detection logic. The `torrent_match` package provides:

1. **Simpler API**: Convenience functions and sensible defaults
2. **Automatic Configuration**: Reads from environment variables
3. **CLI Interface**: Full command-line access to all features
4. **Better Ergonomics**: Easier to use in other projects

For more details, see the main README in the parent directory.
