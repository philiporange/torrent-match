# Torrent Metadata Dataset

## Overview

This dataset contains 100,000 torrent metadata samples from video content (movies and TV shows), weighted by peer activity. Each sample includes the torrent name, size, IMDB identifier (when available), content type classification, and a complete listing of files within the torrent.

## Dataset Statistics

- **Total Samples**: 100,000
- **TV Shows**: 73,963 (73.96%)
- **Movies**: 26,037 (26.04%)
- **IMDB Coverage**: 44,187 samples (44.19%)

## Data Structure

The dataset is stored as a JSON array, where each element represents a single torrent with the following schema:

```json
{
  "name": "string",
  "size": integer,
  "imdb_id": "string | null",
  "type": "tv | movie",
  "files": [
    {
      "path": "string",
      "size": integer
    }
  ],
  "sample_id": "string"
}
```

## Field Descriptions

### Root Level

- **`name`** (string)
  The torrent name as stored in the source database. Typically includes media title, release information, quality indicators, and release group tags.

  Examples:
  - `"Talking Tom and Friends S01E22 INTERNAL 720p WEB x264-WEBTUBE"`
  - `"Petes Dragon 2016 720p BluRay DTS x264-FuzerHD"`

- **`size`** (integer)
  Total size of the torrent in bytes. Represents the sum of all file sizes within the torrent.

- **`imdb_id`** (string | null)
  IMDB identifier in the format `ttXXXXXXX` when available, otherwise `null`. Present for approximately 44% of samples.

  Example: `"tt5297368"`

- **`type`** (string)
  Content type classification. One of two values:
  - `"tv"` - Television shows, series, and episodic content
  - `"movie"` - Feature films and standalone video content

  Classification is based on the source database category:
  - TV categories: 205 (TV shows), 208 (HD TV shows)
  - Movie categories: 201 (Movies), 202 (Movies DVDR), 207 (HD Movies)

- **`files`** (array)
  List of all files contained within the torrent, sorted by size in descending order (largest files first). Each file is an object with `path` and `size` fields.

- **`sample_id`** (string)
  A 16-character hexadecimal hash derived from the SHA256 of the sample's deterministically-sorted JSON representation (excluding the `sample_id` field itself). This identifier is stable and can be used for deduplication or tracking samples across different datasets.

  Example: `"c01c4ab5e603fce9"`

### File Objects

Each object in the `files` array contains:

- **`path`** (string)
  The relative file path within the torrent. May include directory structure.

  Examples:
  - `"Talking.Tom.and.Friends.S01E22.INTERNAL.720p.WEB.x264-WEBTUBE.mkv"`
  - `"Screens/screen0004.jpg"`
  - `"Torrent Downloaded From www.torrenting.org.txt"`

- **`size`** (integer)
  File size in bytes.

## Example Records

### TV Show Sample

```json
{
  "name": "Talking Tom and Friends S01E22 INTERNAL 720p WEB x264-WEBTUBE",
  "size": 147967360,
  "imdb_id": "tt5297368",
  "type": "tv",
  "files": [
    {
      "path": "Talking.Tom.and.Friends.S01E22.INTERNAL.720p.WEB.x264-WEBTUBE.mkv",
      "size": 147340057
    },
    {
      "path": "Screens/screen0004.jpg",
      "size": 143402
    },
    {
      "path": "Screens/screen0003.jpg",
      "size": 128666
    },
    {
      "path": "Talking.Tom.and.Friends.S01E22.INTERNAL.720p.WEB.x264-WEBTUBE.nfo",
      "size": 1221
    },
    {
      "path": "Torrent Downloaded From www.torrenting.org.txt",
      "size": 86
    }
  ],
  "sample_id": "c01c4ab5e603fce9"
}
```

### Movie Sample

```json
{
  "name": "Petes Dragon 2016 720p BluRay DTS x264-FuzerHD",
  "size": 6320617725,
  "imdb_id": null,
  "type": "movie",
  "files": [
    {
      "path": "Petes Dragon 2016 720p BluRay DTS x264-FuzerHD.mkv",
      "size": 6320612578
    },
    {
      "path": "Petes Dragon 2016 720p BluRay DTS x264-FuzerHD.mkv.nfo",
      "size": 5063
    },
    {
      "path": "Torrent Downloaded From Torrenting.com.txt",
      "size": 84
    }
  ],
  "sample_id": "21ac4fbd82ad9a6c"
}
```

## Sampling Methodology

Samples were selected using a peer-weighted random sampling algorithm that favors torrents with higher peer counts (seeders + leechers). The weighting function applies multiplicative boosts based on peer count percentiles:

- **p75+**: 2× boost
- **p90+**: 5× boost
- **p95+**: 11× boost
- **p99+**: 21× boost

This approach ensures the dataset contains a representative mix of popular, well-seeded content while maintaining diversity through the randomization component.

## Data Quality Notes

- **Fileless Torrents**: All samples contain at least one file record. Torrents without file listings were excluded during sampling.

- **File Ordering**: Files within each torrent are sorted by size in descending order for consistency.

- **Type Classification**: The `type` field is derived from database categories and may not always perfectly reflect content nature. For example, some mini-series might be classified as movies, and some TV movies might be classified as TV shows.

- **IMDB Coverage**: Approximately 56% of samples lack IMDB identifiers. Coverage is higher for movies (~60%) than TV shows (~38%).

- **Release Metadata**: Torrent names often contain rich metadata about quality (720p, 1080p), codec (x264, x265), audio (DTS, AAC), and release group, which can be extracted via parsing.

## Use Cases

This dataset is suitable for:

- Training media type classifiers (TV vs movie)
- Extracting structured metadata from torrent names (titles, seasons, episodes, years, quality)
- Analyzing file naming conventions and directory structures
- Building IMDB matching/linking systems
- Understanding torrent packaging patterns
- Training models for media metadata extraction and normalization

## License

CC0 - Public Domain
