# Torrent Sampling Tool

A peer-weighted sampling tool for extracting representative torrent metadata from a SQLite database of video torrents. Samples are weighted toward torrents with higher peer counts (seeders + leechers), and support filtering by content type (TV shows vs movies).

## Overview

`sample.py` connects to a torrent database (`/tmp/test/test.sqlite`) in read-only mode and samples torrents from video categories with configurable filters. The sampling algorithm favors torrents with more active peers, making it ideal for building datasets focused on popular or well-seeded content.

By default, torrents without file listings are excluded to ensure downstream parsing has sufficient metadata.

## Requirements

- Python 3.10+
- peewee ORM library
- SQLite database at `/tmp/test/test.sqlite`
- Peer statistics file at `/tmp/test/peer_stats.json` (optional, uses defaults if missing)

## Installation

```bash
# Install dependencies (if not already installed)
pip install peewee
```

## Usage

### Basic Usage

Sample 10 torrents (default):
```bash
python sample.py
```

Sample a specific number of torrents:
```bash
python sample.py --limit 50
```

### Content Type Filtering

**TV shows only:**
```bash
python sample.py --limit 20 --tv
```

**Movies only:**
```bash
python sample.py --limit 20 --movie
```

**Mixed with specific ratio:**
```bash
# 60% TV, 40% movies
python sample.py --limit 100 --split-tv-film 0.6:0.4

# Or use integer ratios (4 parts TV, 3 parts movies)
python sample.py --limit 100 --split-tv-film 4:3
```

### Additional Options

**Include torrents without file listings:**
```bash
python sample.py --limit 20 --include-fileless
```

**Add deterministic sample IDs:**
```bash
python sample.py --limit 20 --sample-id
```

**Include additional categories:**
```bash
python sample.py --limit 20 --include-category 200 --include-category 204
```

## Output Format

The script outputs JSON to stdout. Each sample contains:

```json
{
  "name": "Torrent name",
  "size": 1234567890,
  "imdb_id": "tt1234567",
  "type": "tv",
  "files": [
    {
      "path": "path/to/file.mkv",
      "size": 1234567890
    }
  ],
  "sample_id": "a1b2c3d4e5f6g7h8"
}
```

### Field Descriptions

- **name** (string): Torrent name as stored in the database
- **size** (integer): Total torrent size in bytes
- **imdb_id** (string|null): IMDB identifier if available
- **type** (string): Content type, either `"tv"` or `"movie"`
- **files** (array): List of files in the torrent, sorted by size (descending)
  - **path** (string): File path within the torrent
  - **size** (integer): File size in bytes
- **sample_id** (string, optional): 16-character SHA256 hash for deduplication (only with `--sample-id`)

## Sampling Algorithm

The script uses weighted random sampling based on peer counts:

1. Calculates total peers (seeders + leechers) for each torrent
2. Applies boost multipliers based on peer count percentiles:
   - p75+: boost × 2
   - p90+: boost × 5
   - p95+: boost × 11
   - p99+: boost × 21
3. Samples using `RANDOM() / boost` as the ordering key

This approach heavily favors high-peer torrents while still including some lower-peer content for diversity.

## Category Mapping

**TV Categories:**
- 205: Video: TV shows
- 208: Video: HD - TV shows

**Movie Categories:**
- 201: Video: Movies
- 202: Video: Movies DVDR
- 207: Video: HD - Movies

**Other Video Categories** (default to "movie" type):
- 200: Video (general)
- 204: Video: Movie clips
- 209: Video: 3D

## Examples

### Create a balanced dataset
```bash
python sample.py --limit 1000 --split-tv-film 1:1 --sample-id > dataset.json
```

### Sample high-quality TV shows
```bash
python sample.py --limit 500 --tv > tv_samples.json
```

### Pipe to jq for analysis
```bash
# Count samples by type
python sample.py --limit 100 --split-tv-film 6:4 | jq '[.[] | .type] | group_by(.) | map({type: .[0], count: length})'

# Find largest torrents
python sample.py --limit 50 --movie | jq 'sort_by(.size) | reverse | .[0:10] | .[] | {name, size}'

# Check file count distribution
python sample.py --limit 100 | jq '[.[] | .files | length] | {min: min, max: max, avg: (add/length)}'
```

## Notes

- The script connects to the database in **read-only mode** for safety
- File lists are sorted by size (largest first) for each torrent
- The `--sample-id` hash is computed from the sample data (excluding the sample_id itself), ensuring reproducibility
- Ratio values in `--split-tv-film` are automatically normalized (e.g., `4:3` becomes 57.14% TV, 42.86% movies)
- When using `--split-tv-film`, TV and movie samples are drawn independently, then combined

## See Also

- `models.py` - Peewee ORM definitions for the torrent database
- `analyse_peer_count.py` - Generates peer statistics for sampling weights
- `PLAN.md` - Overall project plan for the torrent interpretation dataset
